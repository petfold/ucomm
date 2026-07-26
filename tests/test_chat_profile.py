"""Chat profile conformance + end-to-end tests (issue K-8, chat profile first)."""

import random
from dataclasses import replace

import pytest
from bee.swarm.keys import PrivateKey

from ucomm import AuthorLog, GenesisError, address_of, merge_causal
from ucomm.envelope import Membership, Ordering, Persistence, Privacy
from ucomm.profiles.chat import ChatChannel, chat_genesis, validate_chat_genesis

ALICE_KEY = PrivateKey.from_hex("11" * 32)
BOB_KEY = PrivateKey.from_hex("22" * 32)
CAROL_KEY = PrivateKey.from_hex("33" * 32)
MALLORY_KEY = PrivateKey.from_hex("44" * 32)


def test_chat_genesis_conforms():
    validate_chat_genesis(chat_genesis("n1"))  # does not raise


def test_wrong_profile_rejected():
    with pytest.raises(GenesisError, match="profile"):
        validate_chat_genesis(replace(chat_genesis("n1"), profile="mail"))


def test_wrong_membership_rejected():
    with pytest.raises(GenesisError, match="membership"):
        validate_chat_genesis(replace(chat_genesis("n1"), membership=Membership.OPEN))


def test_wrong_persistence_rejected():
    with pytest.raises(GenesisError, match="persistence"):
        validate_chat_genesis(replace(chat_genesis("n1"), persistence=Persistence.EPHEMERAL))


def test_wrong_privacy_rejected():
    with pytest.raises(GenesisError, match="privacy"):
        validate_chat_genesis(replace(chat_genesis("n1"), privacy=Privacy.PUBLIC))


def test_wrong_ordering_rejected():
    with pytest.raises(GenesisError, match="ordering"):
        validate_chat_genesis(replace(chat_genesis("n1"), ordering=Ordering.PER_AUTHOR))


def test_two_party_chat_end_to_end():
    genesis = chat_genesis("alice-bob-1")
    channel = ChatChannel(genesis, keys=(ALICE_KEY, BOB_KEY))
    alice, bob = address_of(ALICE_KEY), address_of(BOB_KEY)

    channel.send(alice, "hi bob")
    channel.send(bob, "hi alice")
    channel.send(alice, "how are you?")

    messages = channel.messages()
    assert [env.inline.decode("utf-8") for env in messages] == \
        ["hi bob", "hi alice", "how are you?"]
    assert [env.author for env in messages] == [alice, bob, alice]


def test_send_from_non_member_rejected():
    channel = ChatChannel(chat_genesis("n1"), keys=(ALICE_KEY, BOB_KEY))
    with pytest.raises(ValueError):
        channel.send(address_of(MALLORY_KEY), "hello")


def test_tampered_message_fails_verification_on_read():
    channel = ChatChannel(chat_genesis("n1"), keys=(ALICE_KEY, BOB_KEY))
    alice = address_of(ALICE_KEY)
    original = channel.send(alice, "hi bob")
    tampered = replace(original, inline=b"forged")
    channel._logs[alice] = AuthorLog()
    channel._logs[alice].append(tampered)
    with pytest.raises(ValueError):
        channel.messages()


def test_mark_read_records_and_syncs_read_state():
    channel = ChatChannel(chat_genesis("n1"), keys=(ALICE_KEY, BOB_KEY))
    alice, bob = address_of(ALICE_KEY), address_of(BOB_KEY)

    first = channel.send(alice, "hi bob")
    channel.send(alice, "you there?")
    channel.mark_read(bob, first)

    assert channel.read_state() == {bob: first.event_hash()}
    # Read-state receipts are control-plane and don't show up as messages.
    assert [env.inline.decode("utf-8") for env in channel.messages()] == \
        ["hi bob", "you there?"]


def test_mark_read_last_receipt_wins():
    channel = ChatChannel(chat_genesis("n1"), keys=(ALICE_KEY, BOB_KEY))
    bob = address_of(BOB_KEY)
    first = channel.send(address_of(ALICE_KEY), "one")
    second = channel.send(address_of(ALICE_KEY), "two")

    channel.mark_read(bob, first)
    channel.mark_read(bob, second)

    assert channel.read_state() == {bob: second.event_hash()}


def test_mark_read_from_non_member_rejected():
    channel = ChatChannel(chat_genesis("n1"), keys=(ALICE_KEY, BOB_KEY))
    msg = channel.send(address_of(ALICE_KEY), "hi")
    with pytest.raises(ValueError):
        channel.mark_read(address_of(MALLORY_KEY), msg)


def test_group_chat_message_order_stable_regardless_of_read_order():
    channel = ChatChannel(chat_genesis("group-1"), keys=(ALICE_KEY, BOB_KEY, CAROL_KEY))
    addrs = [address_of(ALICE_KEY), address_of(BOB_KEY), address_of(CAROL_KEY)]
    order = [addrs[0], addrs[1], addrs[2], addrs[0], addrs[2], addrs[1]]
    for i, author in enumerate(order):
        channel.send(author, f"msg{i}")

    first_read = [env.event_hash() for env in channel.messages()]
    # Re-merge the same underlying events shuffled; must land on the same order.
    all_events = [env for log in channel._logs.values() for env in log]
    shuffled = all_events[:]
    random.shuffle(shuffled)

    second_read = [env.event_hash() for env in merge_causal(shuffled)]
    assert first_read == second_read
