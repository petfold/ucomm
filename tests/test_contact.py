"""Out-of-band contact exchange tests (M1)."""

from dataclasses import replace

import pytest
from bee.swarm.keys import PrivateKey

from ucomm import ContactCard, address_of, make_contact_card, sign_envelope, verify_contact_card
from ucomm.envelope import Envelope, EventKind

ALICE_KEY = PrivateKey.from_hex("11" * 32)
BOB_KEY = PrivateKey.from_hex("22" * 32)


def test_make_and_verify_contact_card():
    card = make_contact_card(ALICE_KEY)
    assert card.address == address_of(ALICE_KEY)
    assert verify_contact_card(card)


def test_tampered_address_fails_verification():
    card = make_contact_card(ALICE_KEY)
    forged = replace(card, address=address_of(BOB_KEY))
    assert not verify_contact_card(forged)


def test_tampered_signature_fails_verification():
    card = make_contact_card(ALICE_KEY)
    forged = replace(card, sig="00" * 65)
    assert not verify_contact_card(forged)


def test_garbage_signature_rejected_not_raised():
    card = ContactCard(address=address_of(ALICE_KEY), sig="not-hex")
    assert not verify_contact_card(card)


def test_to_str_from_str_round_trips():
    card = make_contact_card(ALICE_KEY)
    restored = ContactCard.from_str(card.to_str())
    assert restored == card
    assert verify_contact_card(restored)


def test_from_str_rejects_wrong_prefix():
    with pytest.raises(ValueError):
        ContactCard.from_str("not-a-contact-card")


def test_from_str_rejects_missing_separator():
    with pytest.raises(ValueError):
        ContactCard.from_str("ucomm-contact-v1:justanaddress")


def test_envelope_signature_cannot_be_replayed_as_a_contact_card():
    # Domain separation: signing a real envelope must not produce something
    # that also verifies as a contact card for the same address.
    alice = address_of(ALICE_KEY)
    env = sign_envelope(
        Envelope(channel="ch", author=alice, seq=1, kind=EventKind.MESSAGE), ALICE_KEY
    )
    forged_card = ContactCard(address=alice, sig=env.sig)
    assert not verify_contact_card(forged_card)


def test_contact_card_cannot_be_replayed_as_an_envelope_signature():
    from ucomm.signing import verify_envelope

    alice = address_of(ALICE_KEY)
    card = make_contact_card(ALICE_KEY)
    forged_env = replace(
        Envelope(channel="ch", author=alice, seq=1, kind=EventKind.MESSAGE), sig=card.sig
    )
    assert not verify_envelope(forged_env)
