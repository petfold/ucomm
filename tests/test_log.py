"""Causal-DAG merge property tests (issue K-3)."""

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ucomm import AuthorLog, Envelope, EventKind, merge_causal

CHANNEL = "ch"


def _chain(author: str, n: int) -> list[Envelope]:
    """n envelopes by one author, each referencing the previous (a causal chain)."""
    events: list[Envelope] = []
    prev_hash = ()
    for seq in range(1, n + 1):
        env = Envelope(channel=CHANNEL, author=author, seq=seq, kind=EventKind.MESSAGE,
                        refs=prev_hash)
        events.append(env)
        prev_hash = (env.event_hash(),)
    return events


def _dag(n_authors: int, n_per_author: int) -> list[Envelope]:
    """A DAG with several independent per-author chains (no cross-author refs) —
    concurrent by construction, so any total order is a valid topological sort and
    merge must fall back to hash order among them."""
    events = []
    for a in range(n_authors):
        events.extend(_chain(f"author{a}", n_per_author))
    return events


def test_author_log_rejects_non_increasing_seq():
    log = AuthorLog()
    log.append(Envelope(channel=CHANNEL, author="a", seq=1, kind=EventKind.MESSAGE))
    log.append(Envelope(channel=CHANNEL, author="a", seq=2, kind=EventKind.MESSAGE))
    with pytest.raises(ValueError):
        log.append(Envelope(channel=CHANNEL, author="a", seq=2, kind=EventKind.MESSAGE))


def test_merge_respects_causal_order():
    chain = _chain("alice", 5)
    shuffled = chain[:]
    random.shuffle(shuffled)
    merged = merge_causal(shuffled)
    assert merged == chain


def test_merge_is_idempotent_over_duplicates():
    chain = _chain("alice", 3)
    merged = merge_causal(chain + chain)  # every event delivered twice
    assert merged == chain


def test_merge_deterministic_regardless_of_arrival_order():
    events = _dag(n_authors=3, n_per_author=4)
    orders = []
    for _ in range(5):
        shuffled = events[:]
        random.shuffle(shuffled)
        orders.append(merge_causal(shuffled))
    assert all(o == orders[0] for o in orders)


@given(st.integers(min_value=1, max_value=4), st.integers(min_value=1, max_value=5))
def test_merge_ready_set_ordering_is_deterministic(n_authors, n_per_author):
    events = _dag(n_authors, n_per_author)
    assert merge_causal(events) == merge_causal(list(reversed(events)))
