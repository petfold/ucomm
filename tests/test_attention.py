"""Golden decision tests for the policy engine (issue A-1) using Attila's four
canonical examples, plus determinism and ceiling monotonicity checks."""

from ucomm import (AttentionClaim, Envelope, EventKind, Intensity, PolicyState,
                   SenderContext, TimeWindow, decide)

NOW = 1_000_000.0
WINDOW = TimeWindow(start=NOW - 10, end=NOW + 7200)
POLICY = PolicyState(threshold=20)
KNOWN = SenderContext(known_contact=True)


def invitation(importance, urgency, sender="alice", channel="ch", window=WINDOW):
    return Envelope(
        channel=channel, author=sender, seq=1, kind=EventKind.INVITATION,
        attention=AttentionClaim(importance=importance, urgency=urgency, relevance=window),
    )


def test_smoke_from_the_house_breaks_through():
    d = decide(invitation(30, 30), KNOWN, POLICY, NOW)
    assert d.effective_priority == 40  # capped by known-contact ceiling
    assert d.intensity is Intensity.FULL


def test_tennis_schedule_is_filed():
    d = decide(invitation(2, 2), KNOWN, POLICY, NOW)
    assert d.intensity is Intensity.FILED


def test_expired_beer_invitation_never_interrupts():
    stale = TimeWindow(start=NOW - 7200, end=NOW - 1)
    d = decide(invitation(5, 25, window=stale), KNOWN, POLICY, NOW)
    assert d.intensity is Intensity.FILED


def test_muted_channel_offset_suppresses():
    policy = PolicyState(threshold=20, channel_offsets={"ch": -30})
    d = decide(invitation(20, 20), KNOWN, policy, NOW)
    assert d.intensity in (Intensity.FILED, Intensity.BADGE)


def test_stranger_needs_collateral_to_surface():
    stranger = SenderContext(known_contact=False)
    d = decide(invitation(50, 50), stranger, POLICY, NOW)
    assert d.intensity is Intensity.FILED
    bonded = SenderContext(known_contact=False, collateral_valid=True)
    d2 = decide(invitation(50, 50), bonded, POLICY, NOW)
    assert d2.effective_priority > d.effective_priority


def test_determinism():
    env = invitation(10, 15)
    assert decide(env, KNOWN, POLICY, NOW) == decide(env, KNOWN, POLICY, NOW)


def test_ceiling_monotone_in_wot_distance():
    prios = []
    for dist in (1, 2, 3, 4):
        ctx = SenderContext(known_contact=False, wot_distance=dist)
        prios.append(decide(invitation(60, 60), ctx, POLICY, NOW).effective_priority)
    assert prios == sorted(prios, reverse=True)
