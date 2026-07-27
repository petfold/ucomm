"""Mail profile conformance tests."""

from dataclasses import replace

import pytest

from ucomm import GenesisError
from ucomm.envelope import Membership, Ordering, Persistence, Privacy
from ucomm.profiles.mail import mail_genesis, validate_mail_genesis


def test_mail_genesis_conforms():
    validate_mail_genesis(mail_genesis("n1"))  # does not raise


def test_wrong_profile_rejected():
    with pytest.raises(GenesisError, match="profile"):
        validate_mail_genesis(replace(mail_genesis("n1"), profile="chat"))


def test_wrong_membership_rejected():
    with pytest.raises(GenesisError, match="membership"):
        validate_mail_genesis(replace(mail_genesis("n1"), membership=Membership.INVITE))


def test_wrong_persistence_rejected():
    with pytest.raises(GenesisError, match="persistence"):
        validate_mail_genesis(replace(mail_genesis("n1"), persistence=Persistence.EPHEMERAL))


def test_public_and_e2ee_privacy_both_accepted():
    validate_mail_genesis(replace(mail_genesis("n1"), privacy=Privacy.PUBLIC))
    validate_mail_genesis(replace(mail_genesis("n1"), privacy=Privacy.E2EE))


def test_act_privacy_rejected():
    with pytest.raises(GenesisError, match="privacy"):
        validate_mail_genesis(replace(mail_genesis("n1"), privacy=Privacy.ACT))


def test_wrong_ordering_rejected():
    with pytest.raises(GenesisError, match="ordering"):
        validate_mail_genesis(replace(mail_genesis("n1"), ordering=Ordering.PER_AUTHOR))
