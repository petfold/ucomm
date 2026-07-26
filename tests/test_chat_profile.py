"""Chat profile conformance + end-to-end tests (issue K-8, chat profile first)."""

import random
from dataclasses import replace

import pytest

from ucomm import GenesisError
from ucomm.envelope import Membership, Ordering, Persistence, Privacy
from ucomm.profiles.chat import ChatChannel, chat_genesis, validate_chat_genesis


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
    channel = ChatChannel(genesis, members=("alice", "bob"))

    channel.send("alice", "hi bob")
    channel.send("bob", "hi alice")
    channel.send("alice", "how are you?")

    texts = [env.inline.decode("utf-8") for env in channel.messages()]
    assert texts == ["hi bob", "hi alice", "how are you?"]


def test_send_from_non_member_rejected():
    channel = ChatChannel(chat_genesis("n1"), members=("alice", "bob"))
    with pytest.raises(ValueError):
        channel.send("mallory", "hello")


def test_group_chat_message_order_stable_regardless_of_read_order():
    channel = ChatChannel(chat_genesis("group-1"), members=("alice", "bob", "carol"))
    order = ["alice", "bob", "carol", "alice", "carol", "bob"]
    for i, author in enumerate(order):
        channel.send(author, f"msg{i}")

    first_read = [env.event_hash() for env in channel.messages()]
    # Re-merge the same underlying events shuffled; must land on the same order.
    all_events = [env for log in channel._logs.values() for env in log]
    shuffled = all_events[:]
    random.shuffle(shuffled)
    from ucomm import merge_causal

    second_read = [env.event_hash() for env in merge_causal(shuffled)]
    assert first_read == second_read
