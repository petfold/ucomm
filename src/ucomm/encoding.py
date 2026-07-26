"""Canonical byte encoding for kernel records (issue K-1).

Aligned with recordstore's `canonical_bytes` (github.com/petfold/recordstore):
JSON with sorted keys, compact separators, no ASCII-escaping, no NaN/Infinity.
Content addressing makes determinism a correctness requirement here, not a
style choice — two dataclasses with equal field values must encode to the
same bytes and therefore hash to the same id.

This module has no recordstore dependency yet (that import lands with K-4);
it just matches the wire format so ids computed here stay stable once it does.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum

SCHEMA_VERSION = 1


def canonical_bytes(obj: object) -> bytes:
    """Deterministic byte encoding: equal values => equal bytes."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def to_jsonable(obj: object) -> object:
    """Recursively reduce dataclasses/enums/bytes/tuples to JSON-safe values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (tuple, list)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def content_hash(obj: object) -> str:
    """sha256 hex digest of the record's canonical encoding, schema-versioned."""
    wrapped = {"csv": SCHEMA_VERSION, "val": to_jsonable(obj)}
    return hashlib.sha256(canonical_bytes(wrapped)).hexdigest()
