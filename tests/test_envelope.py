from ucomm import Envelope, EventKind, Genesis
from ucomm.envelope import Membership, Ordering, Persistence, Privacy


def chat_genesis(nonce="n1"):
    return Genesis(
        membership=Membership.INVITE, media=("text",), persistence=Persistence.PERMANENT,
        privacy=Privacy.E2EE, ordering=Ordering.CAUSAL_DAG, write_policy="members",
        profile="chat", nonce=nonce,
    )


def test_channel_id_stable_and_nonce_sensitive():
    assert chat_genesis().channel_id() == chat_genesis().channel_id()
    assert chat_genesis("n1").channel_id() != chat_genesis("n2").channel_id()


def test_plane_classification():
    ch = chat_genesis().channel_id()
    msg = Envelope(channel=ch, author="a", seq=1, kind=EventKind.MESSAGE)
    rcpt = Envelope(channel=ch, author="a", seq=2, kind=EventKind.RECEIPT)
    assert not msg.is_control_plane()
    assert rcpt.is_control_plane()
