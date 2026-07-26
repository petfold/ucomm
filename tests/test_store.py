"""recordstore adapter tests (issue K-4)."""

import pytest
from recordstore import MemoryBytesStore, RecordStore

from ucomm import (AttentionClaim, Envelope, EventKind, RecordStoreAuthorLog,
                   TimeWindow, envelope_to_record, record_to_envelope)
from ucomm.envelope import MediaDescriptor

CHANNEL = "ch"


def _store() -> RecordStore:
    return RecordStore(MemoryBytesStore())


def test_round_trip_minimal_envelope():
    env = Envelope(channel=CHANNEL, author="alice", seq=1, kind=EventKind.MESSAGE)
    assert record_to_envelope(envelope_to_record(env)) == env


def test_round_trip_fully_populated_envelope():
    env = Envelope(
        channel=CHANNEL, author="alice", seq=2, kind=EventKind.INVITATION,
        refs=("deadbeef",),
        media=MediaDescriptor(mime="text/plain", size=42, codec=None),
        payload="swarm-ref-abc", inline=b"\x00\x01\xff",
        attention=AttentionClaim(
            importance=10, urgency=5,
            relevance=TimeWindow(start=1.0, end=2.0),
            interactivity=50, expected_duration_s=30, collateral="bond-ref",
        ),
        sig="deadbeefsig",
    )
    assert record_to_envelope(envelope_to_record(env)) == env


def test_append_persists_across_store_reopen():
    store = _store()
    log = RecordStoreAuthorLog(store, CHANNEL, "alice")
    log.append(Envelope(channel=CHANNEL, author="alice", seq=1, kind=EventKind.MESSAGE))
    log.append(Envelope(channel=CHANNEL, author="alice", seq=2, kind=EventKind.MESSAGE))
    root = store.commit()

    reopened = RecordStore.at(root, store._blobs)
    reloaded = RecordStoreAuthorLog(reopened, CHANNEL, "alice")
    assert [e.seq for e in reloaded] == [1, 2]


def test_iteration_order_matches_seq_order_even_for_many_entries():
    store = _store()
    log = RecordStoreAuthorLog(store, CHANNEL, "alice")
    for seq in range(1, 15):
        log.append(Envelope(channel=CHANNEL, author="alice", seq=seq, kind=EventKind.MESSAGE))
    assert [e.seq for e in log] == list(range(1, 15))


def test_rejects_non_increasing_seq():
    store = _store()
    log = RecordStoreAuthorLog(store, CHANNEL, "alice")
    log.append(Envelope(channel=CHANNEL, author="alice", seq=5, kind=EventKind.MESSAGE))
    with pytest.raises(ValueError):
        log.append(Envelope(channel=CHANNEL, author="alice", seq=5, kind=EventKind.MESSAGE))


def test_rejects_foreign_author_or_channel():
    store = _store()
    log = RecordStoreAuthorLog(store, CHANNEL, "alice")
    with pytest.raises(ValueError):
        log.append(Envelope(channel=CHANNEL, author="bob", seq=1, kind=EventKind.MESSAGE))


def test_two_authors_do_not_see_each_others_events():
    store = _store()
    alice = RecordStoreAuthorLog(store, CHANNEL, "alice")
    bob = RecordStoreAuthorLog(store, CHANNEL, "bob")
    alice.append(Envelope(channel=CHANNEL, author="alice", seq=1, kind=EventKind.MESSAGE))
    bob.append(Envelope(channel=CHANNEL, author="bob", seq=1, kind=EventKind.MESSAGE))
    assert [e.author for e in alice] == ["alice"]
    assert [e.author for e in bob] == ["bob"]
