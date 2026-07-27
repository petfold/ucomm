"""ImapMailbox live-fetch-loop tests, against a fake IMAPClient double.

This covers ImapMailbox's own logic (UID tracking, the RFC 3501 section 9
"n:*" quirk, per-author seq numbering) without a real server. It does not
verify IMAPClient's actual wire behavior -- that needs a real mailbox, not
yet available; see the module docstring in ucomm.bridges.imap.
"""

from email.message import EmailMessage

from ucomm.bridges.imap import ImapMailbox, bridge_author
from ucomm.envelope import EventKind

CHANNEL = "mail-ch"
NOW = 1_000_000.0


def _raw_email(sender="alice@example.com", body="hello", subject="hi"):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "bob@example.com"
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


class _FakeImapClient:
    """Minimal IMAPClient double: just enough of the interface
    ImapMailbox uses, backed by an in-memory {uid: raw message} dict."""

    def __init__(self, messages: dict[int, bytes]):
        self._messages = dict(messages)
        self.selected_folder = None
        self.readonly = None
        self.logged_out = False

    def select_folder(self, folder, readonly=False):
        self.selected_folder = folder
        self.readonly = readonly

    def search(self, criteria):
        if criteria == ["ALL"]:
            return list(self._messages.keys())
        _, range_spec = criteria
        lo = int(range_spec.partition(":")[0])
        matching = [uid for uid in self._messages if uid >= lo]
        # RFC 3501 section 9: a real server includes the mailbox's highest
        # UID even when nothing is actually >= lo -- simulate that quirk
        # deliberately so ImapMailbox's filtering is genuinely exercised.
        if not matching and self._messages:
            return [max(self._messages)]
        return matching

    def fetch(self, uids, data):
        return {uid: {b"RFC822": self._messages[uid]} for uid in uids}

    def logout(self):
        self.logged_out = True


def test_fetch_new_returns_empty_for_an_empty_mailbox():
    mailbox = ImapMailbox(_FakeImapClient({}), CHANNEL)
    assert mailbox.fetch_new(NOW) == []


def test_fetch_new_converts_all_messages_on_first_call():
    client = _FakeImapClient({1: _raw_email(), 2: _raw_email(sender="bob@example.com")})
    mailbox = ImapMailbox(client, CHANNEL)
    envelopes = mailbox.fetch_new(NOW)
    assert [e.kind for e in envelopes] == [
        EventKind.MESSAGE, EventKind.INVITATION, EventKind.MESSAGE, EventKind.INVITATION,
    ]


def test_fetch_new_only_returns_new_messages_on_later_calls():
    client = _FakeImapClient({1: _raw_email()})
    mailbox = ImapMailbox(client, CHANNEL)
    first = mailbox.fetch_new(NOW)
    assert len(first) == 2

    client._messages[2] = _raw_email(body="second message")
    second = mailbox.fetch_new(NOW)
    assert len(second) == 2
    assert second[0].inline == b"second message\n"


def test_fetch_new_returns_nothing_when_nothing_new_despite_uid_range_quirk():
    client = _FakeImapClient({1: _raw_email()})
    mailbox = ImapMailbox(client, CHANNEL)
    mailbox.fetch_new(NOW)  # consumes uid 1
    assert mailbox.fetch_new(NOW) == []  # not a re-fetch of uid 1


def test_fetch_new_seq_increments_per_author_independently():
    client = _FakeImapClient({
        1: _raw_email(sender="alice@example.com", subject="one"),
        2: _raw_email(sender="alice@example.com", subject="two"),
        3: _raw_email(sender="bob@example.com", subject="three"),
    })
    mailbox = ImapMailbox(client, CHANNEL)
    envelopes = mailbox.fetch_new(NOW)
    alice = bridge_author("alice@example.com")
    bob = bridge_author("bob@example.com")
    alice_seqs = [e.seq for e in envelopes if e.author == alice]
    bob_seqs = [e.seq for e in envelopes if e.author == bob]
    assert alice_seqs == [1, 2, 3, 4]
    assert bob_seqs == [1, 2]


def test_close_logs_out():
    client = _FakeImapClient({})
    mailbox = ImapMailbox(client, CHANNEL)
    mailbox.close()
    assert client.logged_out
