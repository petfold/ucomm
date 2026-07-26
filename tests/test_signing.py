"""Envelope signing and verification tests (M1: real signatures)."""

from dataclasses import replace

import pytest
from bee.swarm.keys import PrivateKey

from ucomm import Envelope, EventKind, address_of, sign_envelope, verify_envelope

CHANNEL = "ch"

ALICE_KEY = PrivateKey.from_hex("11" * 32)
BOB_KEY = PrivateKey.from_hex("22" * 32)


def _unsigned(author: str, seq: int = 1) -> Envelope:
    return Envelope(channel=CHANNEL, author=author, seq=seq, kind=EventKind.MESSAGE,
                     inline=b"hello")


def test_sign_then_verify_round_trips():
    alice = address_of(ALICE_KEY)
    env = sign_envelope(_unsigned(alice), ALICE_KEY)
    assert env.sig != ""
    assert verify_envelope(env)


def test_unsigned_envelope_fails_verification():
    alice = address_of(ALICE_KEY)
    assert not verify_envelope(_unsigned(alice))


def test_signature_does_not_verify_under_wrong_author():
    alice = address_of(ALICE_KEY)
    bob = address_of(BOB_KEY)
    env = sign_envelope(_unsigned(alice), ALICE_KEY)
    forged = replace(env, author=bob)
    assert not verify_envelope(forged)


def test_tampering_with_signed_content_invalidates_signature():
    alice = address_of(ALICE_KEY)
    env = sign_envelope(_unsigned(alice), ALICE_KEY)
    tampered = replace(env, inline=b"goodbye")
    assert not verify_envelope(tampered)


def test_sign_rejects_mismatched_author():
    bob = address_of(BOB_KEY)
    with pytest.raises(ValueError):
        sign_envelope(_unsigned(bob), ALICE_KEY)


def test_address_of_is_stable_and_key_specific():
    assert address_of(ALICE_KEY) == address_of(ALICE_KEY)
    assert address_of(ALICE_KEY) != address_of(BOB_KEY)


def test_verify_rejects_garbage_signature():
    alice = address_of(ALICE_KEY)
    garbage = replace(_unsigned(alice), sig="not-hex")
    assert not verify_envelope(garbage)
