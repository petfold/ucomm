"""Channel kernel schema: envelope and genesis records (M0 draft).

See docs/DESIGN.md sections 3.2-3.3. Canonical byte encoding lives in
`ucomm.encoding`, aligned with recordstore's format (issue K-1, done).
ChannelId derivation + genesis validation rules (issue K-2, done): a Genesis
is validated before it is hashed, so an invalid parameter vector never gets
a ChannelId. Real signing (`ucomm.signing`, M1) is a separate module so this
one stays free of a crypto dependency; `sig` here is just the wire slot.

Invariant (DESIGN.md section 9): this module must never import ucomm.attention.
AttentionClaim is data; its evaluation lives entirely on the receiver side.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .encoding import content_hash

ChannelId = str
EventHash = str
PubKey = str  # signer's Ethereum-style address (see ucomm.signing), not a raw public key
SwarmRef = str


class EventKind(str, Enum):
    MESSAGE = "message"
    INVITATION = "invitation"
    RECEIPT = "receipt"
    CONTROL = "control"
    PRESENCE = "presence"


class Membership(str, Enum):
    FIXED = "fixed"
    INVITE = "invite"
    OPEN = "open"


class Persistence(str, Enum):
    PERMANENT = "permanent"
    EPHEMERAL = "ephemeral"  # crypto-shredding only; ciphertext persists (DESIGN 8)
    ARCHIVAL_OPTIONAL = "archival-optional"


class Ordering(str, Enum):
    CAUSAL_DAG = "causal-dag"
    PER_AUTHOR = "per-author"
    SEQUENCED = "moderator-sequenced"


class Privacy(str, Enum):
    PUBLIC = "public"
    ACT = "act"
    E2EE = "e2ee"


class MediaKind(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"


class WritePolicy(str, Enum):
    ANYONE = "anyone"
    MEMBERS = "members"
    BROADCASTER = "broadcaster"


# DESIGN.md section 4 profile table. Unlike the closed-set fields above
# (typed as Enums), profile names stay open-ended -- apps are meant to be
# able to register new blessed profiles without touching the kernel -- so
# this is a whitelist checked in Genesis.validate() instead of a type.
BLESSED_PROFILES = frozenset(
    {"mail", "chat", "call", "open-band", "broadcast", "social", "forum"}
)


class GenesisError(ValueError):
    """A Genesis record fails validation (issue K-2)."""


@dataclass(frozen=True)
class TimeWindow:
    """Relevance window; requests self-expire after `end` (unix seconds)."""

    start: float
    end: float

    def active(self, now: float) -> bool:
        return self.start <= now <= self.end


@dataclass(frozen=True)
class AttentionClaim:
    """Sender-declared, ADVISORY attention request (ATTENTION.md section 1).

    importance/urgency are in additive log-scale units. collateral references a
    bond or stamp proof; verification is receiver-side.
    """

    importance: int
    urgency: int
    relevance: TimeWindow
    interactivity: int = 0  # 0..100
    expected_duration_s: int | None = None
    collateral: str | None = None

    @property
    def claimed_priority(self) -> int:
        return self.importance + self.urgency


@dataclass(frozen=True)
class MediaDescriptor:
    mime: str
    size: int | None = None
    codec: str | None = None


@dataclass(frozen=True)
class Genesis:
    """Channel parameter vector, fixed at creation (DESIGN.md section 3.3).

    ChannelId = hash(canonical encoding of this record).
    """

    membership: Membership
    media: tuple[MediaKind, ...]  # subset of MediaKind (DESIGN.md section 3.3)
    persistence: Persistence
    privacy: Privacy
    ordering: Ordering
    write_policy: WritePolicy
    rate_limit_per_epoch: int | None = None
    suggested_priority_offset: int = 0  # advisory (DESIGN.md section 9)
    profile: str | None = None  # blessed profile name, e.g. "chat" (DESIGN 4)
    nonce: str = ""

    def validate(self) -> None:
        """Raise GenesisError if this record's parameter vector is malformed.

        Closed-set fields (membership, persistence, ordering, privacy, media,
        write_policy) are typed as Enums; a wrong *value* there is a type
        error at construction time, not something this method re-checks.
        What's left is the structural/range constraints Python's type system
        can't express, plus `profile`, which is deliberately an open string
        (see BLESSED_PROFILES) rather than an Enum. Not exhaustive cross-field
        policy either -- that's the profile conformance harness, issue K-8.
        """
        if not self.nonce:
            raise GenesisError(
                "nonce must be non-empty (distinguishes otherwise-identical "
                "channels; an empty nonce would let two unrelated channels "
                "with the same parameter vector collide on ChannelId)"
            )
        if not self.media:
            raise GenesisError("media must declare at least one kind")
        if self.rate_limit_per_epoch is not None and self.rate_limit_per_epoch <= 0:
            raise GenesisError("rate_limit_per_epoch must be positive if set")
        if self.profile is not None and self.profile not in BLESSED_PROFILES:
            raise GenesisError(f"unknown profile: {self.profile!r}")

    def channel_id(self) -> ChannelId:
        self.validate()
        return content_hash(self)


@dataclass(frozen=True)
class Envelope:
    """One event on one channel; the unit of both planes (DESIGN.md section 3.2)."""

    channel: ChannelId
    author: PubKey
    seq: int
    kind: EventKind
    refs: tuple[EventHash, ...] = ()
    media: MediaDescriptor | None = None
    payload: SwarmRef | None = None
    inline: bytes | None = None
    attention: AttentionClaim | None = None
    sig: str = ""  # hex signature; see ucomm.signing.sign_envelope/verify_envelope

    def event_hash(self) -> EventHash:
        # NOTE for when real signing lands: this hashes `sig` along with
        # everything else, which is fine while `sig` is always "" but is the
        # wrong shape for a real signature -- a signer needs the hash of the
        # *unsigned* fields to sign, and refs (which point to event_hash)
        # shouldn't shift depending on signature bytes. Splitting this into
        # an unsigned-content hash + a separate signed EventHash is part of
        # wiring up real signatures, not a change to make speculatively now.
        return content_hash(self)

    def is_control_plane(self) -> bool:
        return self.kind in (
            EventKind.INVITATION,
            EventKind.RECEIPT,
            EventKind.CONTROL,
            EventKind.PRESENCE,
        )
