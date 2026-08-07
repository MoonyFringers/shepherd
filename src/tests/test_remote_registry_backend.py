# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from remote.registry_backend import (
    RegistryBackend,
    _chunk_digest_from_path,
    _chunk_shard_from_prefix,
    _path_to_tag,
)

_HOST = "registry.example.com"
_CHUNK_HASH = "ab" + "3f" * 31  # 64-char hex, shard "ab"
_CHUNK_PATH = f"chunks/ab/{_CHUNK_HASH}"
_LATEST_PATH = "envs/my-env/latest.json"
_DATA = b"some compressed chunk bytes"


def _resp(
    status_code: int = 200,
    json_body: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    content: bytes = b"",
) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.headers = headers or {}
    m.links = {}
    m.content = content
    m.json.return_value = json_body or {}
    m.raise_for_status = MagicMock()
    return m


def _make_backend(session: MagicMock, insecure: bool = True) -> RegistryBackend:
    backend = RegistryBackend(
        host=_HOST, root_path="shepherd", insecure=insecure
    )
    backend._session = session
    return backend


# ---------------------------------------------------------------------------
# _path_to_tag
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_path_to_tag_replaces_slashes() -> None:
    assert _path_to_tag(_CHUNK_PATH) == f"chunks_ab_{_CHUNK_HASH}"
    assert _path_to_tag("index/index.json") == "index_index.json"


@pytest.mark.remote
def test_path_to_tag_replaces_colons() -> None:
    """Snapshot ids embed an ISO-8601 timestamp (e.g. 2026-08-07T21:00:00Z),
    which contains ':' — illegal in an OCI tag."""
    path = "envs/my-env/snapshots/2026-08-07T21:00:00Z-6b22b1.json"
    tag = _path_to_tag(path)
    assert ":" not in tag
    assert tag == "envs_my-env_snapshots_2026-08-07T21_00_00Z-6b22b1.json"


# ---------------------------------------------------------------------------
# _chunk_digest_from_path / _chunk_shard_from_prefix
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_chunk_digest_from_path_matches_chunk() -> None:
    assert _chunk_digest_from_path(_CHUNK_PATH) == f"sha256:{_CHUNK_HASH}"


@pytest.mark.remote
def test_chunk_digest_from_path_matches_tmp_variant() -> None:
    assert (
        _chunk_digest_from_path(f"{_CHUNK_PATH}.tmp") == f"sha256:{_CHUNK_HASH}"
    )


@pytest.mark.remote
def test_chunk_digest_from_path_rejects_index_file() -> None:
    assert _chunk_digest_from_path("chunks/ab/.index.json") is None


@pytest.mark.remote
def test_chunk_digest_from_path_rejects_non_chunk_paths() -> None:
    assert _chunk_digest_from_path(_LATEST_PATH) is None
    assert _chunk_digest_from_path("chunks/ab/tooshort") is None


@pytest.mark.remote
def test_chunk_shard_from_prefix() -> None:
    assert _chunk_shard_from_prefix("chunks/ab") == "ab"
    assert _chunk_shard_from_prefix("chunks/ab/") is None
    assert _chunk_shard_from_prefix("envs/my-env/snapshots") is None


# ---------------------------------------------------------------------------
# exists / upload / download
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_exists_chunk_is_single_blob_head() -> None:
    """Chunk paths encode their own digest — no manifest GET needed."""
    session = MagicMock()
    session.request.return_value = _resp(200)  # HEAD blob
    backend = _make_backend(session)
    assert backend.exists(_CHUNK_PATH) is True
    calls = session.request.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "HEAD"
    assert calls[0][0][1].endswith(f"/blobs/sha256:{_CHUNK_HASH}")


@pytest.mark.remote
def test_exists_chunk_false_when_blob_missing() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    assert backend.exists(_CHUNK_PATH) is False


@pytest.mark.remote
def test_exists_true_when_manifest_and_blob_present() -> None:
    session = MagicMock()
    manifest = {
        "layers": [{"mediaType": "x", "digest": f"sha256:{_CHUNK_HASH}"}]
    }
    session.request.side_effect = [
        _resp(200, json_body=manifest),  # GET manifest (resolve digest)
        _resp(200),  # HEAD blob
    ]
    backend = _make_backend(session)
    assert backend.exists(_LATEST_PATH) is True


@pytest.mark.remote
def test_exists_false_when_manifest_missing() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    assert backend.exists(_LATEST_PATH) is False


@pytest.mark.remote
def test_upload_chunk_pushes_blob_only_no_manifest() -> None:
    session = MagicMock()
    digest = f"sha256:{hashlib.sha256(_DATA).hexdigest()}"
    session.request.side_effect = [
        _resp(404),  # HEAD blob -> not present
        _resp(202, headers={"Location": "/v2/shepherd/blobs/uploads/xyz"}),
        _resp(201),  # PUT blob
    ]
    backend = _make_backend(session)
    backend.upload(_CHUNK_PATH, _DATA)

    calls = session.request.call_args_list
    assert len(calls) == 3
    assert calls[0][0][0] == "HEAD"
    assert calls[1][0][0] == "POST"
    put_blob_call = calls[2]
    assert put_blob_call[0][0] == "PUT"
    assert digest in put_blob_call[0][1]


@pytest.mark.remote
def test_upload_chunk_skips_blob_when_already_present() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(200),  # HEAD blob -> already present
    ]
    backend = _make_backend(session)
    backend.upload(_CHUNK_PATH, _DATA)

    calls = session.request.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "HEAD"


@pytest.mark.remote
def test_upload_non_chunk_pushes_blob_then_manifest() -> None:
    session = MagicMock()
    digest = f"sha256:{hashlib.sha256(_DATA).hexdigest()}"
    session.request.side_effect = [
        _resp(404),  # HEAD blob -> not present
        _resp(202, headers={"Location": "/v2/shepherd/blobs/uploads/xyz"}),
        _resp(201),  # PUT blob
        _resp(404),  # HEAD empty-config blob -> not present
        _resp(202, headers={"Location": "/v2/shepherd/blobs/uploads/abc"}),
        _resp(201),  # PUT empty-config blob
        _resp(201),  # PUT manifest
    ]
    backend = _make_backend(session)
    backend.upload(_LATEST_PATH, _DATA)

    calls = session.request.call_args_list
    assert calls[0][0][0] == "HEAD"
    assert calls[1][0][0] == "POST"
    put_blob_call = calls[2]
    assert put_blob_call[0][0] == "PUT"
    assert digest in put_blob_call[0][1]
    put_manifest_call = calls[-1]
    assert put_manifest_call[0][0] == "PUT"
    assert put_manifest_call[0][1].endswith(
        f"/manifests/{_path_to_tag(_LATEST_PATH)}"
    )


@pytest.mark.remote
def test_upload_non_chunk_skips_blob_when_already_present() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(200),  # HEAD blob -> already present
        _resp(200),  # HEAD empty-config blob -> already present
        _resp(201),  # PUT manifest
    ]
    backend = _make_backend(session)
    backend.upload(_LATEST_PATH, _DATA)

    calls = session.request.call_args_list
    assert len(calls) == 3
    assert calls[0][0][0] == "HEAD"
    assert calls[1][0][0] == "HEAD"
    assert calls[2][0][0] == "PUT"


@pytest.mark.remote
def test_download_chunk_fetches_blob_via_path_digest() -> None:
    session = MagicMock()
    session.request.return_value = _resp(200, content=_DATA)  # GET blob
    backend = _make_backend(session)
    result = backend.download(_CHUNK_PATH)
    assert result == _DATA
    calls = session.request.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "GET"
    assert calls[0][0][1].endswith(f"/blobs/sha256:{_CHUNK_HASH}")


@pytest.mark.remote
def test_download_fetches_blob_via_resolved_digest() -> None:
    session = MagicMock()
    manifest = {
        "layers": [{"mediaType": "x", "digest": f"sha256:{_CHUNK_HASH}"}]
    }
    session.request.side_effect = [
        _resp(200, json_body=manifest),  # GET manifest
        _resp(200, content=_DATA),  # GET blob
    ]
    backend = _make_backend(session)
    result = backend.download(_LATEST_PATH)
    assert result == _DATA


@pytest.mark.remote
def test_download_raises_when_manifest_missing() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    with pytest.raises(FileNotFoundError):
        backend.download(_LATEST_PATH)


# ---------------------------------------------------------------------------
# list_prefix (non-chunk prefixes -> tag-list endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_list_prefix_filters_and_strips_prefix() -> None:
    session = MagicMock()
    tags_body = {
        "tags": [
            "envs_my-env_snapshots_snap-a.json",
            "envs_my-env_snapshots_snap-b.json",
            "envs_other-env_snapshots_snap-c.json",
            "envs_my-env_latest.json",
        ]
    }
    session.request.return_value = _resp(200, json_body=tags_body)
    backend = _make_backend(session)
    result = backend.list_prefix("envs/my-env/snapshots")
    assert sorted(result) == sorted(["snap-a.json", "snap-b.json"])


@pytest.mark.remote
def test_list_prefix_empty_on_404() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    assert backend.list_prefix("envs/my-env/snapshots") == []


@pytest.mark.remote
def test_list_prefix_paginates_via_link_header() -> None:
    session = MagicMock()
    page1 = _resp(
        200,
        json_body={"tags": ["envs_my-env_snapshots_snap-a.json"]},
    )
    page1.links = {
        "next": {"url": "/v2/shepherd/tags/list?n=1000&last=envs_my-env_..."}
    }
    page2 = _resp(
        200, json_body={"tags": ["envs_my-env_snapshots_snap-b.json"]}
    )
    page2.links = {}
    session.request.side_effect = [page1, page2]
    backend = _make_backend(session)
    result = backend.list_prefix("envs/my-env/snapshots")
    assert sorted(result) == sorted(["snap-a.json", "snap-b.json"])
    assert session.request.call_count == 2


# ---------------------------------------------------------------------------
# list_prefix (chunk-shard prefixes -> per-shard .index.json)
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_list_prefix_chunk_shard_reads_persisted_index() -> None:
    session = MagicMock()
    index_manifest = {
        "layers": [{"mediaType": "x", "digest": "sha256:indexdigest"}]
    }
    session.request.side_effect = [
        _resp(200, json_body=index_manifest),  # GET manifest for .index.json
        _resp(200, content=json.dumps([_CHUNK_HASH, "other"]).encode()),
    ]
    backend = _make_backend(session)
    assert sorted(backend.list_prefix("chunks/ab")) == sorted(
        [_CHUNK_HASH, "other"]
    )


@pytest.mark.remote
def test_list_prefix_chunk_shard_empty_when_no_index() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)  # .index.json not found
    backend = _make_backend(session)
    assert backend.list_prefix("chunks/ab") == []


@pytest.mark.remote
def test_list_prefix_chunk_shard_merges_pending_adds_and_removes() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)  # no persisted index yet
    backend = _make_backend(session)
    backend._pending_index_adds["ab"] = {_CHUNK_HASH, "brandnew"}
    backend._pending_index_removes["ab"] = {"brandnew"}
    assert backend.list_prefix("chunks/ab") == [_CHUNK_HASH]


# ---------------------------------------------------------------------------
# delete (chunk paths -> direct blob delete)
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_delete_chunk_removes_blob_directly() -> None:
    session = MagicMock()
    session.request.return_value = _resp(202)  # DELETE blob
    backend = _make_backend(session)
    backend.delete(_CHUNK_PATH)
    calls = session.request.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "DELETE"
    assert calls[0][0][1].endswith(f"/blobs/sha256:{_CHUNK_HASH}")


@pytest.mark.remote
def test_delete_chunk_ignores_registry_that_rejects_delete() -> None:
    session = MagicMock()
    session.request.return_value = _resp(405)
    backend = _make_backend(session)
    backend.delete(_CHUNK_PATH)  # must not raise


@pytest.mark.remote
def test_delete_chunk_updates_pending_index_removes() -> None:
    session = MagicMock()
    session.request.return_value = _resp(202)
    backend = _make_backend(session)
    backend._pending_index_adds["ab"] = {_CHUNK_HASH}
    backend.delete(_CHUNK_PATH)
    assert backend._pending_index_removes["ab"] == {_CHUNK_HASH}
    assert _CHUNK_HASH not in backend._pending_index_adds["ab"]


# ---------------------------------------------------------------------------
# delete (non-chunk paths -> tag+manifest-digest delete)
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_delete_removes_manifest_by_digest() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(200, headers={"Docker-Content-Digest": "sha256:deadbeef"}),
        _resp(202),  # DELETE
    ]
    backend = _make_backend(session)
    backend.delete(_LATEST_PATH)
    calls = session.request.call_args_list
    assert calls[1][0][0] == "DELETE"
    assert calls[1][0][1].endswith("/manifests/sha256:deadbeef")


@pytest.mark.remote
def test_delete_noop_when_manifest_missing() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    backend.delete(_LATEST_PATH)  # must not raise
    assert session.request.call_count == 1  # only the GET, no DELETE


@pytest.mark.remote
def test_delete_ignores_registry_that_rejects_delete() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(200, headers={"Docker-Content-Digest": "sha256:deadbeef"}),
        _resp(405),  # registry disallows manifest deletion
    ]
    backend = _make_backend(session)
    backend.delete(_LATEST_PATH)  # must not raise


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_rename_chunk_is_noop_on_blob_and_indexes_the_hash() -> None:
    """upload(tmp_path, data) already wrote the blob at its permanent
    digest — tmp and final chunk paths share the same hash/digest, so
    there is no blob to move. rename() must not touch the blob at all;
    it only needs to record the chunk as confirmed in its shard index."""
    session = MagicMock()
    backend = _make_backend(session)
    src = f"chunks/ab/{_CHUNK_HASH}.tmp"
    backend._resolve_digest = MagicMock()
    backend.download = MagicMock()  # type: ignore[method-assign]
    backend.upload = MagicMock()  # type: ignore[method-assign]
    backend.delete = MagicMock()  # type: ignore[method-assign]

    backend.rename(src, _CHUNK_PATH)

    backend._resolve_digest.assert_not_called()
    backend.download.assert_not_called()
    backend.upload.assert_not_called()
    backend.delete.assert_not_called()
    assert backend._pending_index_adds["ab"] == {_CHUNK_HASH}


@pytest.mark.remote
def test_rename_chunk_undoes_pending_removal() -> None:
    session = MagicMock()
    backend = _make_backend(session)
    backend._pending_index_removes["ab"] = {_CHUNK_HASH}

    backend.rename(f"chunks/ab/{_CHUNK_HASH}.tmp", _CHUNK_PATH)

    assert _CHUNK_HASH not in backend._pending_index_removes["ab"]
    assert backend._pending_index_adds["ab"] == {_CHUNK_HASH}


@pytest.mark.remote
def test_rename_non_chunk_retags() -> None:
    """rename() for a non-chunk path re-pushes the manifest under the
    destination tag, then removes the source tag. Orchestration only —
    the underlying HTTP sequence for resolve/download/upload/delete is
    covered by their own dedicated tests above."""
    session = MagicMock()
    backend = _make_backend(session)
    backend._resolve_digest = MagicMock(return_value=f"sha256:{_CHUNK_HASH}")
    backend.download = MagicMock(return_value=_DATA)  # type: ignore[method-assign]
    backend.upload = MagicMock()  # type: ignore[method-assign]
    backend.delete = MagicMock()  # type: ignore[method-assign]

    src = "envs/my-env/latest.json.tmp"
    backend.rename(src, _LATEST_PATH)

    backend.download.assert_called_once_with(src)
    backend.upload.assert_called_once_with(_LATEST_PATH, _DATA)
    backend.delete.assert_called_once_with(src)


@pytest.mark.remote
def test_rename_non_chunk_noop_when_src_missing() -> None:
    session = MagicMock()
    session.request.return_value = _resp(404)
    backend = _make_backend(session)
    backend.rename("envs/my-env/latest.json.tmp", _LATEST_PATH)
    assert session.request.call_count == 1


# ---------------------------------------------------------------------------
# Bearer-token auth challenge
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_bearer_challenge_retries_with_token() -> None:
    session = MagicMock()
    challenge = _resp(
        401,
        headers={
            "WWW-Authenticate": (
                'Bearer realm="https://auth.example.com/token",'
                'service="registry.example.com",'
                'scope="repository:shepherd:pull"'
            )
        },
    )
    token_resp = _resp(200, json_body={"token": "test-token"})
    final_resp = _resp(200)

    def request_side_effect(method: str, url: str, **kwargs: Any) -> MagicMock:
        if url.startswith("https://auth.example.com"):
            return token_resp
        if "Authorization" in (kwargs.get("headers") or {}):
            return final_resp
        return challenge

    session.request.side_effect = request_side_effect
    session.get.return_value = token_resp
    backend = _make_backend(session)
    resp = backend._request("HEAD", f"/blobs/sha256:{_CHUNK_HASH}")
    assert resp is final_resp
    session.get.assert_called_once()
    auth_call_kwargs = session.get.call_args[1]
    assert auth_call_kwargs["params"]["service"] == "registry.example.com"
    assert auth_call_kwargs["params"]["scope"] == "repository:shepherd:pull"


@pytest.mark.remote
def test_bearer_challenge_caches_token_across_requests() -> None:
    session = MagicMock()
    challenge = _resp(
        401,
        headers={
            "WWW-Authenticate": (
                'Bearer realm="https://auth.example.com/token",'
                'service="svc",scope="repository:shepherd:pull"'
            )
        },
    )
    token_resp = _resp(200, json_body={"token": "cached-token"})
    ok_resp = _resp(200)

    calls: list[str] = []

    def request_side_effect(method: str, url: str, **kwargs: Any) -> MagicMock:
        if "Authorization" in (kwargs.get("headers") or {}):
            calls.append("authed")
            return ok_resp
        calls.append("challenge")
        return challenge

    session.request.side_effect = request_side_effect
    session.get.return_value = token_resp
    backend = _make_backend(session)

    backend._request("HEAD", "/blobs/sha256:aaa")
    backend._request("HEAD", "/blobs/sha256:bbb")

    # Token endpoint hit only once; subsequent challenges reuse the cache.
    assert session.get.call_count == 1


@pytest.mark.remote
def test_non_bearer_401_returns_original_response() -> None:
    session = MagicMock()
    session.request.return_value = _resp(
        401, headers={"WWW-Authenticate": 'Basic realm="registry"'}
    )
    backend = _make_backend(session)
    resp = backend._request("HEAD", f"/blobs/sha256:{_CHUNK_HASH}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_close_closes_session() -> None:
    session = MagicMock()
    backend = _make_backend(session)
    backend.close()
    session.close.assert_called_once()


@pytest.mark.remote
def test_close_flushes_pending_shard_index() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(404),  # GET manifest for .index.json -> base digest check
        _resp(404),  # GET manifest for .index.json -> read persisted (none)
        _resp(200),  # HEAD index blob -> already present (content varies
        # in practice, but the mock doesn't need to be exact here)
        _resp(200),  # HEAD empty-config blob -> already present
        _resp(404),  # GET manifest for .index.json -> recheck (unchanged)
        _resp(201),  # PUT manifest for .index.json
    ]
    backend = _make_backend(session)
    backend._pending_index_adds["ab"] = {_CHUNK_HASH}

    backend.close()

    calls = session.request.call_args_list
    assert calls[-1][0][0] == "PUT"
    assert calls[-1][0][1].endswith("/manifests/chunks_ab_.index.json")
    session.close.assert_called_once()
    assert backend._pending_index_adds == {}


@pytest.mark.remote
def test_write_shard_index_retries_when_tag_moves_concurrently() -> None:
    """If the index tag's manifest digest changes between the initial
    read and the pre-write recheck (a concurrent writer, e.g. prune()),
    the write must retry with a fresh read/merge instead of blindly
    overwriting the concurrent update."""
    session = MagicMock()
    backend = _make_backend(session)
    backend._pending_index_adds["ab"] = {_CHUNK_HASH}

    # _manifest_digest is consulted twice per attempt (base + recheck):
    # attempt 1 sees "d1" both times (no race) EXCEPT we want the
    # recheck to observe a move, so: base="d1", recheck="d2" (raced);
    # attempt 2: base="d2", recheck="d2" (stable) -> proceeds to PUT.
    backend._manifest_digest = MagicMock(  # type: ignore[method-assign]
        side_effect=["d1", "d2", "d2", "d2"]
    )
    # First read (during the raced attempt) sees {"old"}; second read
    # (after the concurrent writer's change is visible) sees the
    # concurrent writer's update too.
    backend._effective_shard_index = MagicMock(  # type: ignore[method-assign]
        side_effect=[["old"], ["old", "concurrent", _CHUNK_HASH]]
    )
    backend._upload_index_blob = MagicMock(  # type: ignore[method-assign]
        return_value=("sha256:merged", b"merged-bytes")
    )
    backend._put_manifest = MagicMock()  # type: ignore[method-assign]

    backend._write_shard_index("ab")

    # Retried once (four _manifest_digest calls = two attempts), and
    # the write that finally landed used the second (post-race) merge.
    assert backend._manifest_digest.call_count == 4
    assert backend._effective_shard_index.call_count == 2
    backend._put_manifest.assert_called_once()
    assert backend._upload_index_blob.call_args_list[-1] == (
        (["old", "concurrent", _CHUNK_HASH],),
        {},
    )


# ---------------------------------------------------------------------------
# _blob_size
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_blob_size_uses_session_cache_for_freshly_uploaded_chunk() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _resp(404),  # HEAD blob -> not present
        _resp(202, headers={"Location": "/v2/shepherd/blobs/uploads/xyz"}),
        _resp(201),  # PUT blob
    ]
    backend = _make_backend(session)
    digest = f"sha256:{hashlib.sha256(_DATA).hexdigest()}"
    backend.upload(_CHUNK_PATH, _DATA)

    size = backend._blob_size(digest)

    assert size == len(_DATA)
    assert session.request.call_count == 3  # no extra HEAD issued


@pytest.mark.remote
def test_blob_size_falls_back_to_head_for_unknown_digest() -> None:
    session = MagicMock()
    session.request.return_value = _resp(200, headers={"Content-Length": "42"})
    backend = _make_backend(session)

    size = backend._blob_size(f"sha256:{_CHUNK_HASH}")

    assert size == 42
    assert session.request.call_count == 1


# ---------------------------------------------------------------------------
# Per-snapshot OCI image assembly
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_upload_snapshot_manifest_pushes_snapshot_and_latest_image() -> None:
    session = MagicMock()
    snapshot_id = "2026-08-08T00_00_00Z-abc123"
    snapshot_path = f"envs/my-env/snapshots/{snapshot_id}.json"
    other_hash = "cd" + "11" * 31
    snapshot_data = json.dumps(
        {
            "snapshot_id": snapshot_id,
            "environment": "my-env",
            "shepherd_version": "0.0.0",
            "created_at": "2026-08-08T00:00:00Z",
            "chunks": [_CHUNK_HASH, other_hash],
            "chunk_count": 2,
            "total_size_bytes": 100,
            "stored_size_bytes": 80,
        }
    ).encode()

    session.request.side_effect = [
        _resp(404),  # HEAD manifest-json blob -> not present
        _resp(202, headers={"Location": "/v2/shepherd/blobs/uploads/m"}),
        _resp(201),  # PUT manifest-json blob
        _resp(200),  # HEAD empty-config blob -> present
        _resp(201),  # PUT manifest tag for the snapshot-manifest json
        _resp(200, headers={"Content-Length": "10"}),  # HEAD chunk 1 size
        _resp(200, headers={"Content-Length": "20"}),  # HEAD chunk 2 size
        _resp(201),  # PUT snapshot image manifest (per-snapshot tag)
        _resp(201),  # PUT snapshot image manifest (latest tag)
    ]
    backend = _make_backend(session)
    backend.upload(snapshot_path, snapshot_data)

    calls = session.request.call_args_list
    put_calls = [
        c for c in calls if c[0][0] == "PUT" and "/manifests/" in c[0][1]
    ]
    tags = [c[0][1].rsplit("/manifests/", 1)[1] for c in put_calls]
    assert _path_to_tag(snapshot_path) in tags
    assert f"images_my-env_{snapshot_id}" in tags
    assert "images_my-env_latest" in tags

    snapshot_tag_call = next(
        c for c in put_calls if c[0][1].endswith(f"images_my-env_{snapshot_id}")
    )
    pushed_manifest = json.loads(snapshot_tag_call[1]["data"])
    assert [layer["digest"] for layer in pushed_manifest["layers"]] == [
        f"sha256:{_CHUNK_HASH}",
        f"sha256:{other_hash}",
    ]


# ---------------------------------------------------------------------------
# insecure flag controls scheme
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_insecure_uses_http_scheme() -> None:
    backend = RegistryBackend(host=_HOST, root_path="shepherd", insecure=True)
    assert backend._base.startswith("http://")


@pytest.mark.remote
def test_secure_uses_https_scheme() -> None:
    backend = RegistryBackend(host=_HOST, root_path="shepherd", insecure=False)
    assert backend._base.startswith("https://")
