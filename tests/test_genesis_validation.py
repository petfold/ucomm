"""Genesis validation rules (issue K-2)."""

import pytest

from ucomm import Genesis, GenesisError
from ucomm.envelope import Membership, Ordering, Persistence, Privacy


def genesis(**overrides):
    fields = dict(
        membership=Membership.INVITE, media=("text",), persistence=Persistence.PERMANENT,
        privacy=Privacy.E2EE, ordering=Ordering.CAUSAL_DAG, write_policy="members",
        profile="chat", nonce="n1",
    )
    fields.update(overrides)
    return Genesis(**fields)


def test_valid_genesis_derives_channel_id():
    genesis().channel_id()  # does not raise


def test_empty_nonce_rejected():
    with pytest.raises(GenesisError, match="nonce"):
        genesis(nonce="").channel_id()


def test_empty_media_rejected():
    with pytest.raises(GenesisError, match="media"):
        genesis(media=()).channel_id()


def test_unknown_media_kind_rejected():
    with pytest.raises(GenesisError, match="video-8k"):
        genesis(media=("text", "video-8k")).channel_id()


def test_unknown_write_policy_rejected():
    with pytest.raises(GenesisError, match="write_policy"):
        genesis(write_policy="admin-only").channel_id()


def test_non_positive_rate_limit_rejected():
    with pytest.raises(GenesisError, match="rate_limit_per_epoch"):
        genesis(rate_limit_per_epoch=0).channel_id()
    with pytest.raises(GenesisError, match="rate_limit_per_epoch"):
        genesis(rate_limit_per_epoch=-1).channel_id()


def test_positive_rate_limit_accepted():
    genesis(rate_limit_per_epoch=10).channel_id()


def test_unknown_profile_rejected():
    with pytest.raises(GenesisError, match="profile"):
        genesis(profile="not-a-real-profile").channel_id()


def test_no_profile_accepted():
    genesis(profile=None).channel_id()


def test_invalid_genesis_never_produces_a_channel_id():
    bad = genesis(nonce="")
    with pytest.raises(GenesisError):
        bad.channel_id()
