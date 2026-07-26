"""recordstore adapter for per-author logs (issue K-4).

DESIGN.md section 3.1: "recordstore is the natural persistence substrate...
ucomm should be a downstream consumer of recordstore, not a parallel storage
effort." This module is that thin adapter: one recordstore record per
envelope, keyed so the store's native lexicographic key order matches
per-author sequence order — no separate index structure needed.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from recordstore import RecordStore

from .encoding import to_jsonable
from .envelope import (
    AttentionClaim,
    ChannelId,
    Envelope,
    EventKind,
    MediaDescriptor,
    PubKey,
    TimeWindow,
)

_SEQ_WIDTH = 20  # zero-padded so lexicographic key order == numeric seq order


def _key(channel: ChannelId, author: PubKey, seq: int) -> str:
    return f"log/{channel}/{author}/{seq:0{_SEQ_WIDTH}d}"


def _key_prefix(channel: ChannelId, author: PubKey) -> str:
    return f"log/{channel}/{author}/"


def envelope_to_record(env: Envelope) -> dict[str, Any]:
    result = to_jsonable(env)
    assert isinstance(result, dict)
    return result


def record_to_envelope(record: dict[str, Any]) -> Envelope:
    attention: AttentionClaim | None = None
    raw_attention = record.get("attention")
    if raw_attention is not None:
        window = raw_attention["relevance"]
        attention = AttentionClaim(
            importance=raw_attention["importance"], urgency=raw_attention["urgency"],
            relevance=TimeWindow(start=window["start"], end=window["end"]),
            interactivity=raw_attention["interactivity"],
            expected_duration_s=raw_attention["expected_duration_s"],
            collateral=raw_attention["collateral"],
        )
    media: MediaDescriptor | None = None
    raw_media = record.get("media")
    if raw_media is not None:
        media = MediaDescriptor(mime=raw_media["mime"], size=raw_media["size"],
                                 codec=raw_media["codec"])
    inline = record.get("inline")
    if inline is not None:
        inline = bytes.fromhex(inline)
    return Envelope(
        channel=record["channel"], author=record["author"], seq=record["seq"],
        kind=EventKind(record["kind"]), refs=tuple(record["refs"]),
        media=media, payload=record.get("payload"), inline=inline,
        attention=attention, sig=record["sig"],
    )


class RecordStoreAuthorLog:
    """One author's append-only log for one channel, persisted via recordstore.

    Mirrors `ucomm.log.AuthorLog`'s interface (append/__iter__/__len__) so
    callers can swap between the in-memory and recordstore-backed logs; the
    strictly-increasing-seq invariant is enforced the same way. Appends are
    staged on the passed-in `RecordStore`; the caller decides when to
    `commit()` (a log may batch several appends into one commit).
    """

    def __init__(self, store: RecordStore, channel: ChannelId, author: PubKey) -> None:
        self._store = store
        self._channel = channel
        self._author = author
        self._last_seq: int | None = None
        for env in self:
            self._last_seq = env.seq

    def append(self, env: Envelope) -> None:
        if env.channel != self._channel or env.author != self._author:
            raise ValueError("envelope does not belong to this log")
        if self._last_seq is not None and env.seq <= self._last_seq:
            raise ValueError(f"non-increasing seq: {env.seq} after {self._last_seq}")
        self._store.put(_key(self._channel, self._author, env.seq), envelope_to_record(env))
        self._last_seq = env.seq

    def __iter__(self) -> Iterator[Envelope]:
        prefix = _key_prefix(self._channel, self._author)
        for _key_, record in self._store.items(prefix):
            yield record_to_envelope(record)

    def __len__(self) -> int:
        return sum(1 for _ in self)
