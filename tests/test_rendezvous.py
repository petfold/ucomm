"""InMemoryRendezvous tests (issue K-5)."""

from ucomm import Envelope, EventKind, InMemoryRendezvous

CHANNEL = "ch"


def _envelope(seq: int = 1) -> Envelope:
    return Envelope(channel=CHANNEL, author="a", seq=seq, kind=EventKind.MESSAGE)


def test_post_then_poll_round_trips():
    rv = InMemoryRendezvous()
    env = _envelope()
    assert rv.post("box1", env) is True
    assert rv.poll("box1") == [env]


def test_poll_drains_the_box():
    rv = InMemoryRendezvous()
    rv.post("box1", _envelope())
    rv.poll("box1")
    assert rv.poll("box1") == []


def test_poll_on_empty_address_returns_empty_list():
    rv = InMemoryRendezvous()
    assert rv.poll("never-posted-to") == []


def test_addresses_are_isolated():
    rv = InMemoryRendezvous()
    env1, env2 = _envelope(1), _envelope(2)
    rv.post("box1", env1)
    rv.post("box2", env2)
    assert rv.poll("box1") == [env1]
    assert rv.poll("box2") == [env2]


def test_post_preserves_arrival_order():
    rv = InMemoryRendezvous()
    envs = [_envelope(i) for i in range(1, 4)]
    for env in envs:
        rv.post("box1", env)
    assert rv.poll("box1") == envs


def test_admit_hook_can_reject():
    rv = InMemoryRendezvous(admit=lambda address, env: env.author == "allowed")
    blocked = Envelope(channel=CHANNEL, author="blocked", seq=1, kind=EventKind.MESSAGE)
    allowed = Envelope(channel=CHANNEL, author="allowed", seq=1, kind=EventKind.MESSAGE)

    assert rv.post("box1", blocked) is False
    assert rv.post("box1", allowed) is True
    assert rv.poll("box1") == [allowed]


def test_admit_hook_sees_the_target_address():
    seen = []
    rv = InMemoryRendezvous(admit=lambda address, env: seen.append(address) or True)
    rv.post("mailbox-42", _envelope())
    assert seen == ["mailbox-42"]
