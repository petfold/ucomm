"""Live integration test against a real IMAP mailbox (issue D-5, live fetch).

Skipped unless UCOMM_IMAP_HOST, UCOMM_IMAP_USERNAME, and
UCOMM_IMAP_PASSWORD are set -- this hits a real mailbox, so it's opt-in,
not part of the default offline suite. Read-only: connects with
`select_folder(..., readonly=True)`, never modifies anything.

Cannot assert specific mailbox content (it's a real inbox, whatever's in
it varies), so this is a shape/smoke test: connecting and fetching doesn't
raise, and if there's at least one message, the message/invitation
pairing and hashes line up the same way the offline tests already prove
against a fake client.
"""

from __future__ import annotations

import os
import time

import pytest

from ucomm.bridges.imap import ImapMailbox
from ucomm.envelope import EventKind

IMAP_HOST = os.environ.get("UCOMM_IMAP_HOST")
IMAP_USERNAME = os.environ.get("UCOMM_IMAP_USERNAME")
IMAP_PASSWORD = os.environ.get("UCOMM_IMAP_PASSWORD")
IMAP_FOLDER = os.environ.get("UCOMM_IMAP_FOLDER", "INBOX")

pytestmark = pytest.mark.skipif(
    not (IMAP_HOST and IMAP_USERNAME and IMAP_PASSWORD),
    reason="live IMAP integration needs UCOMM_IMAP_HOST, UCOMM_IMAP_USERNAME, "
           "UCOMM_IMAP_PASSWORD (UCOMM_IMAP_FOLDER optional, defaults to INBOX)",
)


def test_connects_and_fetches_a_real_mailbox_read_only():
    channel = "ucomm-imap-test"
    mailbox = ImapMailbox.connect(
        IMAP_HOST, IMAP_USERNAME, IMAP_PASSWORD, channel, folder=IMAP_FOLDER,
    )
    try:
        envelopes = mailbox.fetch_new(time.time())
    finally:
        mailbox.close()

    assert isinstance(envelopes, list)
    if not envelopes:
        return  # empty mailbox -- nothing more to check

    kinds = [e.kind for e in envelopes]
    assert kinds == [EventKind.MESSAGE, EventKind.INVITATION] * (len(envelopes) // 2)
    for message_env, invitation in zip(envelopes[::2], envelopes[1::2]):
        assert invitation.refs == (message_env.event_hash(),)
        assert invitation.author == message_env.author
