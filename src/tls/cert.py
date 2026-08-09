# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""
Local certificate authority and leaf-certificate issuance.

Design (see ADR-0008): a single self-signed CA lives under
`${SHPD_PATH}/ca/`, generated once and manually trusted by the user. Its
`NameConstraints` extension is scoped to a caller-supplied set of DNS
domains, so a CA trusted on the user's machine cannot be abused to mint
certificates for arbitrary hostnames. Per-environment leaf certificates are
issued against a caller-supplied SAN list and reissued only when that SAN
set changes or the certificate is nearing expiry -- never from "currently
running" state, to avoid reissue storms.

This module is domain-agnostic: it knows nothing about ingress, proxies, or
Docker. It is a leaf utility, callable by any future plugin/core feature
that needs HTTPS certificates for containers it manages.
"""

from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from util.util import Util

if TYPE_CHECKING:
    from config import ConfigMng

CA_KEY_FILENAME = "ca.key"
CA_CERT_FILENAME = "ca.crt"
CA_LOCK_FILENAME = ".lock"
LEAF_DIR_NAME = "leaf"
LEAF_KEY_FILENAME = "leaf.key"
LEAF_CERT_FILENAME = "leaf.crt"
LEAF_META_FILENAME = "leaf.json"

# Bounded lifetimes: an unbounded, manually-trusted root that the user will
# never remember to remove is worse than a bounded one that forces a
# deliberate `tls rotate`. Leaf certs are reissued automatically well before
# their shorter lifetime expires.
CA_VALIDITY_DAYS = 3650
LEAF_VALIDITY_DAYS = 90
LEAF_REISSUE_MARGIN_DAYS = 14

CA_KEY_SIZE = 4096
LEAF_KEY_SIZE = 2048


class TlsError(RuntimeError):
    """Base class for `tls` subsystem errors."""


class CaNotInitializedError(TlsError):
    """Raised when an operation needs the CA but `ensure_ca` was never
    called."""


@dataclass(frozen=True)
class CaInfo:
    cert_path: str
    key_path: str
    fingerprint_sha256: str
    not_after: datetime.datetime


@dataclass(frozen=True)
class LeafCert:
    env_tag: str
    cert_path: str
    key_path: str
    sans: tuple[str, ...]
    not_after: datetime.datetime


def _atomic_write_bytes(path: str, data: bytes, *, mode: int) -> None:
    """Write `data` to `path` atomically (`tempfile` + `os.replace`) with
    `mode` permissions set before the file becomes visible at its final
    name, so a concurrent reader never observes a partially-written or
    wrongly-permissioned file."""
    directory = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _sha256_fingerprint(cert: x509.Certificate) -> str:
    digest = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in digest)


def _sans_hash(sans: Sequence[str]) -> str:
    normalized = sorted(set(sans))
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def _generate_key(key_size: int) -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=key_size)


def _dns_or_ip_name(value: str) -> x509.GeneralName:
    try:
        import ipaddress

        return x509.IPAddress(ipaddress.ip_address(value))
    except ValueError:
        return x509.DNSName(value)


class CertificateAuthorityMng:
    """Manages the local self-signed CA and per-environment leaf
    certificates under `${SHPD_PATH}/ca/`."""

    def __init__(self, configMng: "ConfigMng"):
        self.configMng = configMng

    @property
    def ca_dir(self) -> str:
        return self.configMng.constants.SHPD_CA_DIR

    @property
    def _ca_key_path(self) -> str:
        return os.path.join(self.ca_dir, CA_KEY_FILENAME)

    @property
    def _ca_cert_path(self) -> str:
        return os.path.join(self.ca_dir, CA_CERT_FILENAME)

    @property
    def _lock_path(self) -> str:
        return os.path.join(self.ca_dir, CA_LOCK_FILENAME)

    def _leaf_dir(self, env_tag: str) -> str:
        return os.path.join(self.ca_dir, LEAF_DIR_NAME, env_tag)

    def leaf_cert_paths(self, env_tag: str) -> tuple[str, str]:
        """Return `(cert_path, key_path)` for `env_tag`'s leaf certificate.

        Pure path computation -- deterministic and callable before the
        certificate exists. Lets a caller (e.g. an `IngressProvider`) know
        the final mount paths before `issue_leaf_cert` has actually written
        anything, so a proxy container's volume mounts can reference the
        same paths the certificate will later be issued to."""
        leaf_dir = self._leaf_dir(env_tag)
        return (
            os.path.join(leaf_dir, LEAF_CERT_FILENAME),
            os.path.join(leaf_dir, LEAF_KEY_FILENAME),
        )

    def ca_cert_path(self) -> str:
        """Return the CA certificate's host path (pure path computation,
        same convention as `leaf_cert_paths` -- callable before the CA is
        generated). Callers mounting this into a container (e.g. so a
        probe can trust HTTPS ingress) must ensure `ensure_ca()` has run
        first, or the mount source won't exist."""
        return self._ca_cert_path

    def is_initialized(self) -> bool:
        return os.path.exists(self._ca_key_path) and os.path.exists(
            self._ca_cert_path
        )

    def _locked(self):
        """Context manager: cross-process exclusive lock over CA
        generation, closing the read-check-write race between two
        concurrent `shepctl` invocations sharing the same CA directory."""
        Util.ensure_dir(self.ca_dir, "SHPD_CA_DIR", mode=0o700)
        lock_fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        return _FileLock(lock_fd)

    def ensure_ca(self, permitted_dns_domains: Sequence[str]) -> CaInfo:
        """Idempotently ensure a local CA exists, constrained to
        `permitted_dns_domains`.

        If a CA already exists, it is returned as-is -- the domain list is
        only used the first time a CA is generated. `NameConstraints` is
        immutable once signed, so changing the domain set requires an
        explicit `rotate`.
        """
        if not permitted_dns_domains:
            raise ValueError(
                "ensure_ca requires at least one permitted DNS domain "
                "(NameConstraints must not be empty)."
            )
        with self._locked():
            if self.is_initialized():
                return self._read_ca_info()
            return self._generate_ca(permitted_dns_domains)

    def _generate_ca(self, permitted_dns_domains: Sequence[str]) -> CaInfo:
        key = _generate_key(CA_KEY_SIZE)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "Shepherd Local CA"),
                x509.NameAttribute(
                    NameOID.ORGANIZATION_NAME, "Shepherd Core Stack"
                ),
            ]
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        not_after = now + datetime.timedelta(days=CA_VALIDITY_DAYS)
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(not_after)
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0), critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.NameConstraints(
                    permitted_subtrees=[
                        x509.DNSName(domain) for domain in permitted_dns_domains
                    ],
                    excluded_subtrees=None,
                ),
                critical=True,
            )
        )
        cert = builder.sign(key, hashes.SHA256())

        key_bytes = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)

        _atomic_write_bytes(self._ca_key_path, key_bytes, mode=0o600)
        _atomic_write_bytes(self._ca_cert_path, cert_bytes, mode=0o644)

        return CaInfo(
            cert_path=self._ca_cert_path,
            key_path=self._ca_key_path,
            fingerprint_sha256=_sha256_fingerprint(cert),
            not_after=not_after,
        )

    def _read_ca_info(self) -> CaInfo:
        with open(self._ca_cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return CaInfo(
            cert_path=self._ca_cert_path,
            key_path=self._ca_key_path,
            fingerprint_sha256=_sha256_fingerprint(cert),
            not_after=cert.not_valid_after_utc,
        )

    def fingerprint(self) -> str:
        # Locked like every other CA-reading/writing method: without it, a
        # concurrent `remove()`/`rotate()` can be observed mid-teardown
        # (key file already gone, cert file not yet) and turn into an
        # unhandled `FileNotFoundError` instead of `CaNotInitializedError`.
        with self._locked():
            if not self.is_initialized():
                raise CaNotInitializedError(
                    "No local CA found. Run 'shepctl tls rotate --domain "
                    "<domain>' to generate one."
                )
            return self._read_ca_info().fingerprint_sha256

    def rotate(self, permitted_dns_domains: Sequence[str]) -> CaInfo:
        """Regenerate the CA and invalidate every existing leaf
        certificate (they were signed by the old CA, so they no longer
        chain to the new one). Leaf certs are lazily reissued on the next
        `issue_leaf_cert` call for each environment."""
        if not permitted_dns_domains:
            raise ValueError(
                "rotate requires at least one permitted DNS domain "
                "(NameConstraints must not be empty)."
            )
        with self._locked():
            leaf_root = os.path.join(self.ca_dir, LEAF_DIR_NAME)
            if os.path.isdir(leaf_root):
                for entry in os.listdir(leaf_root):
                    self._remove_leaf_dir(os.path.join(leaf_root, entry))
            return self._generate_ca(permitted_dns_domains)

    def remove(self) -> None:
        """Remove the CA and every leaf certificate. Irreversible: any
        environment relying on issued certificates will need a new CA
        trusted and its leaf certificates reissued."""
        with self._locked():
            for path in (self._ca_key_path, self._ca_cert_path):
                if os.path.exists(path):
                    os.unlink(path)
            leaf_root = os.path.join(self.ca_dir, LEAF_DIR_NAME)
            if os.path.isdir(leaf_root):
                for entry in os.listdir(leaf_root):
                    self._remove_leaf_dir(os.path.join(leaf_root, entry))

    @staticmethod
    def _remove_leaf_dir(path: str) -> None:
        for name in (
            LEAF_KEY_FILENAME,
            LEAF_CERT_FILENAME,
            LEAF_META_FILENAME,
        ):
            candidate = os.path.join(path, name)
            if os.path.exists(candidate):
                os.unlink(candidate)
        if os.path.isdir(path):
            os.rmdir(path)

    def list_envs(self) -> list[str]:
        """Return the tags of environments with a live leaf certificate."""
        # Locked for the same reason as `fingerprint()`: without it, a
        # concurrent `rotate()`/`remove_leaf_cert()` sweep can be observed
        # mid-removal (leaf dir present, cert file already unlinked) and
        # produce a flickering, inconsistent listing instead of a clean
        # before/after snapshot.
        with self._locked():
            leaf_root = os.path.join(self.ca_dir, LEAF_DIR_NAME)
            if not os.path.isdir(leaf_root):
                return []
            return sorted(
                entry
                for entry in os.listdir(leaf_root)
                if os.path.exists(
                    os.path.join(leaf_root, entry, LEAF_CERT_FILENAME)
                )
            )

    def issue_leaf_cert(
        self,
        env_tag: str,
        sans: Sequence[str],
        *,
        validity_days: int = LEAF_VALIDITY_DAYS,
    ) -> LeafCert:
        """Idempotently issue (or reuse) a leaf certificate for `env_tag`
        covering exactly `sans`.

        Reissues only when the SAN set changes or the current certificate
        is within `LEAF_REISSUE_MARGIN_DAYS` of expiring -- never based on
        which containers happen to be running, so one `env up` produces at
        most one issuance regardless of how many probe-gated startup
        cycles it takes.
        """
        if not sans:
            raise ValueError(
                f"issue_leaf_cert for '{env_tag}' requires at least one SAN."
            )

        with self._locked():
            # Checked inside the lock, not before it: an unlocked check here
            # raced with a concurrent `remove()`/`rotate()` can observe the
            # CA as initialized and then hit `FileNotFoundError` opening
            # `_ca_key_path` below once the lock is actually acquired.
            if not self.is_initialized():
                raise CaNotInitializedError(
                    "No local CA found. Call ensure_ca(...) before issuing "
                    "leaf certificates."
                )
            leaf_dir = self._leaf_dir(env_tag)
            existing = self._read_leaf_meta(leaf_dir)
            wanted_hash = _sans_hash(sans)
            if existing is not None:
                not_after = datetime.datetime.fromisoformat(
                    existing["not_after"]
                )
                reissue_at = not_after - datetime.timedelta(
                    days=LEAF_REISSUE_MARGIN_DAYS
                )
                now = datetime.datetime.now(datetime.timezone.utc)
                if existing["sans_hash"] == wanted_hash and now < reissue_at:
                    return LeafCert(
                        env_tag=env_tag,
                        cert_path=os.path.join(leaf_dir, LEAF_CERT_FILENAME),
                        key_path=os.path.join(leaf_dir, LEAF_KEY_FILENAME),
                        sans=tuple(sorted(set(sans))),
                        not_after=not_after,
                    )
            return self._issue_leaf_cert(leaf_dir, env_tag, sans)

    def _read_leaf_meta(self, leaf_dir: str) -> Optional[dict[str, str]]:
        meta_path = os.path.join(leaf_dir, LEAF_META_FILENAME)
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    def _issue_leaf_cert(
        self, leaf_dir: str, env_tag: str, sans: Sequence[str]
    ) -> LeafCert:
        Util.ensure_dir(leaf_dir, f"SHPD_CA_LEAF_DIR[{env_tag}]", mode=0o700)

        with open(self._ca_key_path, "rb") as f:
            loaded_key = serialization.load_pem_private_key(f.read(), None)
        if not isinstance(loaded_key, RSAPrivateKey):
            raise TlsError(
                f"CA key at '{self._ca_key_path}' is not an RSA key; "
                "the CA directory may be corrupt. Run 'shepctl tls "
                "rotate' to regenerate it."
            )
        ca_key: RSAPrivateKey = loaded_key
        with open(self._ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())

        key = _generate_key(LEAF_KEY_SIZE)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, env_tag)])
        now = datetime.datetime.now(datetime.timezone.utc)
        not_after = now + datetime.timedelta(days=LEAF_VALIDITY_DAYS)
        san_list = sorted(set(sans))
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(not_after)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName(
                    [_dns_or_ip_name(name) for name in san_list]
                ),
                critical=False,
            )
        )
        cert = builder.sign(ca_key, hashes.SHA256())

        key_bytes = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)

        cert_path = os.path.join(leaf_dir, LEAF_CERT_FILENAME)
        key_path = os.path.join(leaf_dir, LEAF_KEY_FILENAME)
        meta_path = os.path.join(leaf_dir, LEAF_META_FILENAME)

        _atomic_write_bytes(key_path, key_bytes, mode=0o600)
        _atomic_write_bytes(cert_path, cert_bytes, mode=0o644)
        _atomic_write_bytes(
            meta_path,
            json.dumps(
                {
                    "sans_hash": _sans_hash(san_list),
                    "not_after": not_after.isoformat(),
                }
            ).encode("utf-8"),
            mode=0o600,
        )

        return LeafCert(
            env_tag=env_tag,
            cert_path=cert_path,
            key_path=key_path,
            sans=tuple(san_list),
            not_after=not_after,
        )

    def remove_leaf_cert(self, env_tag: str) -> None:
        """Remove `env_tag`'s leaf certificate, e.g. on environment
        deletion. A no-op if none exists."""
        with self._locked():
            self._remove_leaf_dir(self._leaf_dir(env_tag))


class _FileLock:
    """`flock`-based cross-process mutual exclusion, released on context
    exit or process death (never left held by a crashed process)."""

    def __init__(self, fd: int):
        self._fd = fd

    def __enter__(self) -> "_FileLock":
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc_info: object) -> None:
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
