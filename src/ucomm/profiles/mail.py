"""Mail profile (DESIGN.md section 4).

The mail row of the profile table: 1:few, async (interactivity 0), permanent,
optional E2EE, per-message invitation granularity -- unlike chat's standing
channel-level accept, anyone can send you mail without joining anything
first, the same way real email works. That's `membership=OPEN`,
`write_policy=ANYONE`.
"""

from __future__ import annotations

from ..envelope import (
    Genesis,
    GenesisError,
    MediaKind,
    Membership,
    Ordering,
    Persistence,
    Privacy,
    WritePolicy,
)


def mail_genesis(nonce: str, rate_limit_per_epoch: int | None = None) -> Genesis:
    """Construct a genesis satisfying the mail profile; nonce distinguishes channels."""
    return Genesis(
        membership=Membership.OPEN, media=(MediaKind.TEXT,),
        persistence=Persistence.PERMANENT, privacy=Privacy.PUBLIC,
        ordering=Ordering.CAUSAL_DAG, write_policy=WritePolicy.ANYONE,
        rate_limit_per_epoch=rate_limit_per_epoch, profile="mail", nonce=nonce,
    )


def validate_mail_genesis(genesis: Genesis) -> None:
    """Raise GenesisError unless `genesis` conforms to the mail profile row."""
    genesis.validate()
    if genesis.profile != "mail":
        raise GenesisError(f"not a mail-profile genesis: profile={genesis.profile!r}")
    if genesis.membership != Membership.OPEN:
        raise GenesisError("mail profile requires open membership")
    if genesis.persistence != Persistence.PERMANENT:
        raise GenesisError("mail profile requires permanent persistence")
    if genesis.privacy not in (Privacy.PUBLIC, Privacy.E2EE):
        raise GenesisError("mail profile allows public or E2EE privacy only")
    if genesis.ordering != Ordering.CAUSAL_DAG:
        raise GenesisError("mail profile requires causal-DAG ordering")
    if genesis.write_policy != WritePolicy.ANYONE:
        raise GenesisError("mail profile requires write_policy=anyone")
