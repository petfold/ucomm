"""IMAP bridge: envelope adapter for email (issue D-5).

DESIGN.md section 10: bridges convert an external protocol's events into
the same envelope schema and policy engine ucomm uses natively, so the
attention firewall covers inboxes that already exist. This module is the
**pure conversion layer only**: raw email -> envelope(s), fully offline and
unit-testable with synthetic messages (stdlib `email` objects) -- no
network. The live fetch loop (connecting to a real mailbox via
`IMAPClient`, per CLAUDE.md's "use established libraries, not raw
`imaplib`" convention) is separate, still-open work. Same shape as the
kernel shipping before `ucomm.bee`: the conversion logic is worth having
and testing on its own first.

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
"""

from __future__ import annotations

import hashlib
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import cast

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
