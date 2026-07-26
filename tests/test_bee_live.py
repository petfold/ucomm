"""Live integration test against a real Bee node (issue: M1 feed I/O).

Skipped unless UCOMM_BEE_API_URL and UCOMM_BEE_POSTAGE_BATCH_ID are set --
this hits a real network and (via the postage batch's already-spent xBZZ)
real Swarm storage, so it's opt-in, not part of the default offline suite.
The batch must already be bought and usable (immutable, per CLAUDE.md);
this test never buys one.
"""

from __future__ import annotations

import os

import pytest
from bee.swarm.keys import PrivateKey

from ucomm.bee import open_author_feed_log
from ucomm.envelope import Envelope, EventKind
from ucomm.signing import address_of, sign_envelope, verify_envelope

BEE_API_URL = os.environ.get("UCOMM_BEE_API_URL")
POSTAGE_BATCH_ID = os.environ.get("UCOMM_BEE_POSTAGE_BATCH_ID")

pytestmark = pytest.mark.skipif(
    not (BEE_API_URL and POSTAGE_BATCH_ID),
    reason="live Bee integration needs UCOMM_BEE_API_URL and UCOMM_BEE_POSTAGE_BATCH_ID",
)


def test_author_log_round_trips_through_a_real_feed():
    channel = "ucomm-test-" + os.urandom(4).hex()
    key = PrivateKey(os.urandom(32))
    author = address_of(key)

    store, log = open_author_feed_log(
        BEE_API_URL, channel, signer_hex=key.to_hex(), postage_batch_id=POSTAGE_BATCH_ID,
    )
    assert len(log) == 0

    unsigned = Envelope(
        channel=channel, author=author, seq=1, kind=EventKind.MESSAGE,
        inline=b"hello swarm",
    )
    signed = sign_envelope(unsigned, key)
    log.append(signed)
    store.commit()

    # Open a fresh store/log pointed at the same feed -- a different reader
    # -- to confirm the write is durable on Swarm, not just a local artifact.
    _reopened_store, reopened_log = open_author_feed_log(
        BEE_API_URL, channel, signer_hex=key.to_hex(), postage_batch_id=POSTAGE_BATCH_ID,
    )
    events = list(reopened_log)
    assert events == [signed]
    assert verify_envelope(events[0])
