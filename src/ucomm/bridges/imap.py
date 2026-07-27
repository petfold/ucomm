"""IMAP bridge: envelope adapter for email (issue D-5).

DESIGN.md section 10: bridges convert an external protocol's events into
the same envelope schema and policy engine ucomm uses natively, so the
attention firewall covers inboxes that already exist. This module has two
layers:

- **Pure conversion** (`envelope_from_email`, `invitation_for_email`,
  `bridge_author`): raw email -> envelope(s), fully offline and
  unit-testable with synthetic messages (stdlib `email` objects) -- no
  network. This is the part with real test coverage against arbitrary
  input.
- **Live fetch** (`ImapMailbox`): connects to a real mailbox via
  `IMAPClient` (per CLAUDE.md's "use established libraries, not raw
  `imaplib`" convention) and calls the pure layer per message. This part
  is only unit-tested against a fake client double -- it hasn't been
  verified against a real IMAP server yet (no test mailbox available when
  this was written), the same caveat `ucomm.bee` had before its first live
  Bee run.

Bridged authorship is NOT the same guarantee as a native ucomm signature.
An email's `From:` address is only as trustworthy as SMTP/DKIM made it --
ucomm doesn't re-verify that. Bridged envelopes are left unsigned
(`sig=""`); `verify_envelope` on one is always `False`, honestly, never
silently treated as verified.

Every bridged email gets a paired `INVITATION` (DESIGN.md section 3.2, two
planes -- the message body is content, the invitation is a small pointer
to it, `refs`-only, no payload duplication) with a naive default
`AttentionClaim`. That claim is exactly as advisory as any sender's claim
ever is (CLAUDE.md invariant 1): the receiver's own policy engine decides
how loud a bridged email actually is, not the quality of this default.

This bridge is read-only by design (IMAP fetch only, `select_folder(...,
readonly=True)`) -- it ingests existing mail into the unified dashboard,
it does not send. Composing/replying would need SMTP, a distinct and
separate capability this module doesn't provide.
"""

from __future__ import annotations

import hashlib
from email import message_from_bytes
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import cast

from imapclient import IMAPClient

from ..envelope import (
    AttentionClaim,
    ChannelId,
    Envelope,
    EventHash,
    EventKind,
    MediaDescriptor,
    PubKey,
    TimeWindow,
)

_BRIDGE_AUTHOR_PREFIX = "bridge:imap:"

DEFAULT_RELEVANCE_SECONDS = 7 * 24 * 3600  # a week: mail is async, not urgent by default


def bridge_author(email_address: str) -> PubKey:
    """A deterministic, clearly-namespaced pseudo-author for a bridged sender.

    Not a real signing key's address -- visibly different in shape (a
    `bridge:imap:` prefix) so it can never be confused with, or collide
    with, one. Bridged envelopes are unsigned; nothing should treat this
    as an authenticated identity.
    """
    digest = hashlib.sha256(email_address.strip().lower().encode("utf-8")).hexdigest()
    return f"{_BRIDGE_AUTHOR_PREFIX}{digest}"


def _extract_body(msg: Message) -> tuple[str, str]:
    """Return (mime type, text) for the best available non-attachment part.

    Prefers text/plain over text/html, matching the mail profile's
    text-only media declaration; either can be added properly (real
    multipart/attachment media kinds) once a profile needs it.
    """
    if msg.is_multipart():
        for wanted in ("text/plain", "text/html"):
            for part in msg.walk():
                if part.get_content_type() == wanted and not part.get_filename():
                    # get_payload(decode=True) always returns bytes|None here;
                    # the stub's wider return type doesn't narrow on `decode`.
                    payload = cast("bytes | None", part.get_payload(decode=True)) or b""
                    charset = part.get_content_charset() or "utf-8"
                    return wanted, payload.decode(charset, errors="replace")
        return "text/plain", ""
    payload = cast("bytes | None", msg.get_payload(decode=True)) or b""
    charset = msg.get_content_charset() or "utf-8"
    return msg.get_content_type() or "text/plain", payload.decode(charset, errors="replace")


def _received_at(msg: Message, *, default: float) -> float:
    date_header = msg.get("Date")
    if date_header:
        try:
            return parsedate_to_datetime(date_header).timestamp()
        except (TypeError, ValueError):
            pass
    return default


def envelope_from_email(
    msg: Message, channel: ChannelId, seq: int, refs: tuple[EventHash, ...] = (),
) -> Envelope:
    """Convert one email into a `MESSAGE` envelope. Pure; no network."""
    sender = msg.get("From", "")
    mime, body = _extract_body(msg)
    return Envelope(
        channel=channel, author=bridge_author(sender), seq=seq,
        kind=EventKind.MESSAGE, refs=refs,
        media=MediaDescriptor(mime=mime), inline=body.encode("utf-8"),
    )


def invitation_for_email(
    msg: Message, channel: ChannelId, seq: int, message_hash: EventHash, now: float,
    *, importance: int = 5, urgency: int = 5,
    relevance_seconds: float = DEFAULT_RELEVANCE_SECONDS,
) -> Envelope:
    """The paired attention request for a bridged email.

    `refs=(message_hash,)` only -- a small pointer to the message envelope,
    never the body itself (two planes, CLAUDE.md invariant 3). `now` is the
    fallback "received at" when the email has no parseable `Date:` header.
    """
    sender = msg.get("From", "")
    received = _received_at(msg, default=now)
    return Envelope(
        channel=channel, author=bridge_author(sender), seq=seq,
        kind=EventKind.INVITATION, refs=(message_hash,),
        attention=AttentionClaim(
            importance=importance, urgency=urgency,
            relevance=TimeWindow(start=received, end=received + relevance_seconds),
        ),
    )


class ImapMailbox:
    """Live IMAP fetch loop: pulls new mail via `IMAPClient` and converts
    each message with the pure functions above.

    Uses UIDs, not sequence numbers, to track what's new -- UIDs are
    stable across sessions per IMAP semantics, sequence numbers aren't.
    Fetch state (last-seen UID, next `seq` per bridged author) lives on
    this object, in-process only; persisting it across restarts (so a
    fresh run doesn't re-fetch everything) is separate, not-yet-built
    work -- the same "in-memory first" step `AuthorLog` went through
    before `RecordStoreAuthorLog`.
    """

    def __init__(self, client: IMAPClient, channel: ChannelId) -> None:
        self._client = client
        self.channel = channel
        self._last_uid: int | None = None
        self._next_seq: dict[PubKey, int] = {}

    @classmethod
    def connect(
        cls, host: str, username: str, password: str, channel: ChannelId,
        *, folder: str = "INBOX", port: int | None = None, ssl: bool = True,
    ) -> ImapMailbox:
        """Connect, log in, and select `folder` read-only -- this bridge
        only ever reads (see the module docstring: composing/sending
        would need SMTP, which this doesn't provide)."""
        client = IMAPClient(host, port=port, ssl=ssl, use_uid=True)
        client.login(username, password)
        client.select_folder(folder, readonly=True)
        return cls(client, channel)

    def close(self) -> None:
        self._client.logout()

    def fetch_new(self, now: float) -> list[Envelope]:
        """Fetch and convert messages newer than the last call.

        Advances internal state; safe to call repeatedly as a poll loop.
        Returns a flat `[message, invitation, message, invitation, ...]`
        list, in the shape `ucomm.daemon.build_dashboard`/
        `directory_read_state` already expect as one channel's events.
        """
        uids = self._new_uids()
        if not uids:
            return []
        fetched = self._client.fetch(uids, ["RFC822"])
        envelopes: list[Envelope] = []
        for uid in uids:
            msg = message_from_bytes(fetched[uid][b"RFC822"])
            author = bridge_author(msg.get("From", ""))
            seq = self._next_seq.get(author, 1)
            message_env = envelope_from_email(msg, self.channel, seq)
            invitation = invitation_for_email(
                msg, self.channel, seq + 1, message_env.event_hash(), now,
            )
            envelopes.extend((message_env, invitation))
            self._next_seq[author] = seq + 2
            self._last_uid = uid
        return envelopes

    def _new_uids(self) -> list[int]:
        if self._last_uid is None:
            return sorted(self._client.search(["ALL"]))
        uids = self._client.search(["UID", f"{self._last_uid + 1}:*"])
        # RFC 3501 section 9: a "n:*" range is defined to include the
        # mailbox's highest UID even when nothing is actually >= n --
        # filter that back out rather than re-processing the top message
        # on every poll that finds nothing new.
        return sorted(uid for uid in uids if uid > self._last_uid)
