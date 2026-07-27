"""Per-author append-only logs and causal-DAG merge (issue K-3).

DESIGN.md section 3.1: a channel is per-author logs + a merge rule + a
genesis parameter vector fixed at creation. This module gives the
`Ordering.CAUSAL_DAG` merge rule: a deterministic topological sort over
envelopes' `refs` (causal parents). Ties among concurrent events (no causal
path between them) are broken by ascending `event_hash`, so any two readers
who have received the same set of events converge on the same order
regardless of arrival order — the property that lets merge run locally with
no lock server (DESIGN.md section 3.1).

`Ordering.PER_AUTHOR` and `Ordering.SEQUENCED` are separate merge rules
(concatenate-by-author, moderator-assigned order) and are not yet
implemented — only `CAUSAL_DAG` is needed for the chat profile (M1).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .envelope import Envelope, EventHash, EventKind, PubKey


class AuthorLog:
    """A single author's append-only log for one channel.

    Enforces the one invariant a log must hold locally: an author's own
    sequence numbers strictly increase. Causal completeness (whether a
    ref'd event has actually been seen) is `merge_causal`'s concern, not
    the log's — a reader may append events whose refs aren't resolved yet.
    """

    def __init__(self) -> None:
        self._events: list[Envelope] = []

    def append(self, env: Envelope) -> None:
        if self._events and env.seq <= self._events[-1].seq:
            raise ValueError(f"non-increasing seq: {env.seq} after {self._events[-1].seq}")
        self._events.append(env)

    def __iter__(self) -> Iterator[Envelope]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)


def merge_causal(envelopes: Iterable[Envelope]) -> list[Envelope]:
    """Deterministic topological sort of envelopes by causal refs.

    Duplicate deliveries (same event_hash) are deduplicated, so merge is
    idempotent over the multiset a reader has collected from all member
    logs. Refs pointing outside the given set (already-pruned or not-yet-
    fetched events) are treated as already satisfied.

    The cycle check below is a defensive backstop, not a case that occurs
    with honest data: since a ref is the *hash* of its target's content, an
    event can never (short of a hash collision) reference something whose
    content includes that same event.
    """
    by_hash: dict[EventHash, Envelope] = {}
    for env in envelopes:
        by_hash.setdefault(env.event_hash(), env)

    remaining = dict(by_hash)
    ordered: list[Envelope] = []
    while remaining:
        ready = sorted(
            h for h, env in remaining.items()
            if all(ref not in remaining for ref in env.refs)
        )
        if not ready:
            raise ValueError("cycle detected in causal refs")
        for h in ready:
            ordered.append(remaining.pop(h))
    return ordered


def read_state(events: Iterable[Envelope]) -> dict[PubKey, EventHash]:
    """Latest event hash each author has acknowledged, from `RECEIPT` events.

    This is the kernel-level convention for DESIGN.md section 10's "read-
    state is a synced event kind": a `RECEIPT`'s `inline` is the hex-encoded
    hash of the event it acknowledges (a small pointer, not payload data --
    CLAUDE.md invariant 3). It's a kernel convention rather than a chat-
    profile one because `RECEIPT` is a kernel `EventKind`, not something a
    profile defines; any profile using `RECEIPT` should mean the same thing
    by it, which is what lets `ucomm.daemon` aggregate read-state across
    every channel in the directory regardless of profile (issue D-3).

    Doesn't require the input to be merge-ordered -- last write by `seq`
    would need ordering, but "last receipt wins" here just means the last
    one encountered in `events`, so callers pass already-merged events
    (`merge_causal`'s output) to get the actually-latest acknowledgment.
    """
    state: dict[PubKey, EventHash] = {}
    for env in events:
        if env.kind is EventKind.RECEIPT and env.inline is not None:
            state[env.author] = env.inline.decode("ascii")
    return state
