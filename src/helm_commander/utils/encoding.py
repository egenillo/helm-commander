"""Base64 / gzip encode-decode helpers for Helm release data."""

from __future__ import annotations

import base64
import gzip
import json


def decode_release_secret(data: bytes) -> dict:
    """Decode a Helm release from a Kubernetes Secret.

    Pipeline: base64 → gzip → utf-8 → json.
    Some kubernetes client versions do not auto-decode the outer base64
    layer, resulting in a double-encoded payload.  We detect this by
    checking for the gzip magic number after the first decode.
    """
    decoded = base64.b64decode(data)
    if decoded[:2] != b'\x1f\x8b':
        decoded = base64.b64decode(decoded)
    decompressed = gzip.decompress(decoded)
    return json.loads(decompressed.decode("utf-8"))


def decode_release_configmap(data: str) -> dict:
    """Decode a Helm release from a ConfigMap.

    ConfigMap values are plain strings, so there is an extra base64 layer.

    Pipeline: base64 → base64 → gzip → utf-8 → json.
    """
    first = base64.b64decode(data.encode("utf-8"))
    second = base64.b64decode(first)
    decompressed = gzip.decompress(second)
    return json.loads(decompressed.decode("utf-8"))


def encode_release(payload: dict) -> str:
    """Encode a release dict back to base64+gzip (for tests)."""
    raw = json.dumps(payload).encode("utf-8")
    compressed = gzip.compress(raw)
    return base64.b64encode(compressed).decode("ascii")
