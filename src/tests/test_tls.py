# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Unit tests for :class:`~tls.cert.CertificateAuthorityMng`."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding

from tls.cert import (
    LEAF_META_FILENAME,
    CaNotInitializedError,
    CertificateAuthorityMng,
)
from util.constants import Constants


class _FakeConfigMng:
    def __init__(self, shpd_path: str):
        self.constants = Constants(
            SHPD_CONFIG_VALUES_FILE=os.path.join(shpd_path, ".shpd.conf"),
            SHPD_PATH=shpd_path,
            LOG_FILE=os.path.join(shpd_path, "log"),
            LOG_LEVEL="INFO",
            RAW_LOG_STDOUT="false",
            LOG_FORMAT="%(message)s",
        )


@pytest.fixture
def ca_mng(tmp_path: Path) -> CertificateAuthorityMng:
    return CertificateAuthorityMng(_FakeConfigMng(str(tmp_path)))


def _verify_signed_by(
    leaf_cert: x509.Certificate, ca_cert: x509.Certificate
) -> None:
    ca_cert.public_key().verify(
        leaf_cert.signature,
        leaf_cert.tbs_certificate_bytes,
        padding.PKCS1v15(),
        leaf_cert.signature_hash_algorithm,
    )


@pytest.mark.tls
def test_not_initialized_by_default(ca_mng: CertificateAuthorityMng):
    assert ca_mng.is_initialized() is False
    assert ca_mng.list_envs() == []
    with pytest.raises(CaNotInitializedError):
        ca_mng.fingerprint()


@pytest.mark.tls
def test_ensure_ca_requires_at_least_one_domain(
    ca_mng: CertificateAuthorityMng,
):
    with pytest.raises(ValueError):
        ca_mng.ensure_ca([])


@pytest.mark.tls
def test_ensure_ca_generates_ca_with_expected_permissions(
    ca_mng: CertificateAuthorityMng,
):
    info = ca_mng.ensure_ca(["sslip.io"])

    assert ca_mng.is_initialized() is True
    assert oct(os.stat(ca_mng.ca_dir).st_mode & 0o777) == "0o700"
    assert oct(os.stat(info.key_path).st_mode & 0o777) == "0o600"
    assert info.fingerprint_sha256 == ca_mng.fingerprint()


@pytest.mark.tls
def test_ca_cert_path_matches_ensure_ca_output(
    ca_mng: CertificateAuthorityMng,
):
    """`ca_cert_path()` is a pure path calculation, usable before or after
    the CA exists, and matches where `ensure_ca()` actually writes it."""
    path_before = ca_mng.ca_cert_path()
    assert not os.path.exists(path_before)

    info = ca_mng.ensure_ca(["sslip.io"])

    assert ca_mng.ca_cert_path() == path_before == info.cert_path
    assert os.path.exists(ca_mng.ca_cert_path())


@pytest.mark.tls
def test_ensure_ca_is_idempotent(ca_mng: CertificateAuthorityMng):
    info1 = ca_mng.ensure_ca(["sslip.io"])
    info2 = ca_mng.ensure_ca(["a-different-domain.example"])

    assert info1.fingerprint_sha256 == info2.fingerprint_sha256


@pytest.mark.tls
def test_ensure_ca_sets_name_constraints(ca_mng: CertificateAuthorityMng):
    info = ca_mng.ensure_ca(["sslip.io", "internal.example"])

    with open(info.cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    name_constraints = cert.extensions.get_extension_for_class(
        x509.NameConstraints
    )
    permitted = {
        name.value for name in name_constraints.value.permitted_subtrees or []
    }
    assert permitted == {"sslip.io", "internal.example"}
    basic_constraints = cert.extensions.get_extension_for_class(
        x509.BasicConstraints
    )
    assert basic_constraints.value.ca is True


@pytest.mark.tls
def test_issue_leaf_cert_requires_ca(ca_mng: CertificateAuthorityMng):
    with pytest.raises(CaNotInitializedError):
        ca_mng.issue_leaf_cert("test-1", ["web-test-1.sslip.io"])


@pytest.mark.tls
def test_issue_leaf_cert_requires_at_least_one_san(
    ca_mng: CertificateAuthorityMng,
):
    ca_mng.ensure_ca(["sslip.io"])
    with pytest.raises(ValueError):
        ca_mng.issue_leaf_cert("test-1", [])


@pytest.mark.tls
def test_issue_leaf_cert_signed_by_ca_with_matching_sans(
    ca_mng: CertificateAuthorityMng,
):
    ca_info = ca_mng.ensure_ca(["sslip.io"])
    sans = ["web-test-1.sslip.io", "api-test-1.sslip.io"]

    leaf = ca_mng.issue_leaf_cert("test-1", sans)

    assert oct(os.stat(leaf.key_path).st_mode & 0o777) == "0o600"
    assert leaf.sans == tuple(sorted(sans))

    with open(ca_info.cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(leaf.cert_path, "rb") as f:
        leaf_cert = x509.load_pem_x509_certificate(f.read())

    _verify_signed_by(leaf_cert, ca_cert)

    san_ext = leaf_cert.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    )
    assert set(san_ext.value.get_values_for_type(x509.DNSName)) == set(sans)

    assert ca_mng.list_envs() == ["test-1"]


@pytest.mark.tls
def test_issue_leaf_cert_reuses_when_sans_unchanged(
    ca_mng: CertificateAuthorityMng,
):
    ca_mng.ensure_ca(["sslip.io"])
    sans = ["web-test-1.sslip.io"]

    leaf1 = ca_mng.issue_leaf_cert("test-1", sans)
    with open(leaf1.cert_path, "rb") as f:
        bytes1 = f.read()

    leaf2 = ca_mng.issue_leaf_cert("test-1", sans)
    with open(leaf2.cert_path, "rb") as f:
        bytes2 = f.read()

    assert bytes1 == bytes2


@pytest.mark.tls
def test_issue_leaf_cert_reissues_when_sans_change(
    ca_mng: CertificateAuthorityMng,
):
    ca_mng.ensure_ca(["sslip.io"])

    leaf1 = ca_mng.issue_leaf_cert("test-1", ["web-test-1.sslip.io"])
    with open(leaf1.cert_path, "rb") as f:
        bytes1 = f.read()

    leaf2 = ca_mng.issue_leaf_cert(
        "test-1", ["web-test-1.sslip.io", "api-test-1.sslip.io"]
    )
    with open(leaf2.cert_path, "rb") as f:
        bytes2 = f.read()

    assert bytes1 != bytes2
    assert leaf2.sans == ("api-test-1.sslip.io", "web-test-1.sslip.io")


@pytest.mark.tls
def test_issue_leaf_cert_reissues_when_nearing_expiry(
    ca_mng: CertificateAuthorityMng,
):
    ca_mng.ensure_ca(["sslip.io"])
    sans = ["web-test-1.sslip.io"]
    leaf1 = ca_mng.issue_leaf_cert("test-1", sans)
    with open(leaf1.cert_path, "rb") as f:
        bytes1 = f.read()

    # Simulate the certificate being close to expiry without waiting on
    # real time: same SAN set, but the stored metadata now claims the
    # certificate expires tomorrow, which is inside the reissue margin.
    meta_path = os.path.join(
        os.path.dirname(leaf1.cert_path), LEAF_META_FILENAME
    )
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["not_after"] = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1)
    ).isoformat()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)

    leaf2 = ca_mng.issue_leaf_cert("test-1", sans)
    with open(leaf2.cert_path, "rb") as f:
        bytes2 = f.read()

    assert bytes1 != bytes2


@pytest.mark.tls
def test_remove_leaf_cert(ca_mng: CertificateAuthorityMng):
    ca_mng.ensure_ca(["sslip.io"])
    ca_mng.issue_leaf_cert("test-1", ["web-test-1.sslip.io"])
    assert ca_mng.list_envs() == ["test-1"]

    ca_mng.remove_leaf_cert("test-1")

    assert ca_mng.list_envs() == []


@pytest.mark.tls
def test_remove_leaf_cert_is_a_noop_when_missing(
    ca_mng: CertificateAuthorityMng,
):
    ca_mng.ensure_ca(["sslip.io"])
    ca_mng.remove_leaf_cert("never-issued")  # must not raise


@pytest.mark.tls
def test_rotate_requires_at_least_one_domain(ca_mng: CertificateAuthorityMng):
    ca_mng.ensure_ca(["sslip.io"])
    with pytest.raises(ValueError):
        ca_mng.rotate([])


@pytest.mark.tls
def test_rotate_regenerates_ca_and_clears_leaf_certs(
    ca_mng: CertificateAuthorityMng,
):
    info1 = ca_mng.ensure_ca(["sslip.io"])
    ca_mng.issue_leaf_cert("test-1", ["web-test-1.sslip.io"])
    assert ca_mng.list_envs() == ["test-1"]

    info2 = ca_mng.rotate(["sslip.io"])

    assert info2.fingerprint_sha256 != info1.fingerprint_sha256
    assert ca_mng.list_envs() == []


@pytest.mark.tls
def test_remove_clears_ca_and_leaf_certs(ca_mng: CertificateAuthorityMng):
    ca_mng.ensure_ca(["sslip.io"])
    ca_mng.issue_leaf_cert("test-1", ["web-test-1.sslip.io"])

    ca_mng.remove()

    assert ca_mng.is_initialized() is False
    assert ca_mng.list_envs() == []
    with pytest.raises(CaNotInitializedError):
        ca_mng.fingerprint()
