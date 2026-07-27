"""IMAP bridge conversion tests (issue D-5, pure layer only)."""

from email.message import EmailMessage

from ucomm.bridges.imap import bridge_author, envelope_from_email, invitation_for_email
from ucomm.envelope import EventKind
from ucomm.signing import verify_envelope

CHANNEL = "mail-ch"
NOW = 1_000_000.0


def _plain_email(body="hello there", sender="alice@example.com", date=None):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "bob@example.com"
    msg["Subject"] = "hi"
    if date is not None:
        msg["Date"] = date
    msg.set_content(body)
    return msg


def _html_only_email(html="<p>hello</p>", sender="alice@example.com"):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "bob@example.com"
    msg["Subject"] = "hi"
    msg.set_content(html, subtype="html")
    return msg


def _multipart_with_plain_and_html(plain="plain body", html="<p>html body</p>",
                                    sender="alice@example.com"):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "bob@example.com"
    msg["Subject"] = "hi"
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return msg


def test_bridge_author_deterministic():
    assert bridge_author("alice@example.com") == bridge_author("alice@example.com")


def test_bridge_author_differs_per_sender():
    assert bridge_author("alice@example.com") != bridge_author("bob@example.com")


def test_bridge_author_case_and_whitespace_insensitive():
    assert bridge_author(" Alice@Example.com ") == bridge_author("alice@example.com")


def test_bridge_author_is_namespaced():
    assert bridge_author("alice@example.com").startswith("bridge:imap:")


def test_envelope_from_email_plain_text():
    msg = _plain_email(body="hello there")
    env = envelope_from_email(msg, CHANNEL, seq=1)
    assert env.channel == CHANNEL
    assert env.seq == 1
    assert env.kind is EventKind.MESSAGE
    assert env.author == bridge_author("alice@example.com")
    assert env.media.mime == "text/plain"
    assert env.inline.decode("utf-8").strip() == "hello there"
    assert env.sig == ""


def test_envelope_from_email_multipart_prefers_plain_text():
    msg = _multipart_with_plain_and_html()
    env = envelope_from_email(msg, CHANNEL, seq=1)
    assert env.media.mime == "text/plain"
    assert "plain body" in env.inline.decode("utf-8")


def test_envelope_from_email_html_only_falls_back_to_html():
    msg = _html_only_email(html="<p>hello</p>")
    env = envelope_from_email(msg, CHANNEL, seq=1)
    assert env.media.mime == "text/html"
    assert "<p>hello</p>" in env.inline.decode("utf-8")


def test_bridged_envelope_is_unsigned_and_fails_verification():
    env = envelope_from_email(_plain_email(), CHANNEL, seq=1)
    assert not verify_envelope(env)


def test_invitation_refs_message_hash_only_no_payload():
    msg = _plain_email()
    message_env = envelope_from_email(msg, CHANNEL, seq=1)
    invitation = invitation_for_email(msg, CHANNEL, seq=2, message_hash=message_env.event_hash(),
                                       now=NOW)
    assert invitation.kind is EventKind.INVITATION
    assert invitation.refs == (message_env.event_hash(),)
    assert invitation.payload is None
    assert invitation.inline is None
    assert invitation.media is None


def test_invitation_uses_date_header_when_present():
    msg = _plain_email(date="Mon, 01 Jan 2024 12:00:00 +0000")
    invitation = invitation_for_email(msg, CHANNEL, seq=2, message_hash="deadbeef", now=NOW)
    assert invitation.attention.relevance.start == 1704110400.0


def test_invitation_falls_back_to_now_without_date_header():
    msg = _plain_email(date=None)
    invitation = invitation_for_email(msg, CHANNEL, seq=2, message_hash="deadbeef", now=NOW)
    assert invitation.attention.relevance.start == NOW


def test_invitation_claim_is_advisory_default_not_hardcoded_forever():
    msg = _plain_email()
    invitation = invitation_for_email(
        msg, CHANNEL, seq=2, message_hash="deadbeef", now=NOW, importance=50, urgency=50,
    )
    assert invitation.attention.claimed_priority == 100
