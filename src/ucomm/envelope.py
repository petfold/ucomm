"""Channel kernel schema: envelope and genesis records (M0 draft).

See docs/DESIGN.md sections 3.2-3.3. Canonical byte encoding lives in
`ucomm.encoding`, aligned with recordstore's format (issue K-1, done).
ChannelId derivation + genesis validation rules (issue K-2, done): a Genesis
is validated before it is hashed, so an invalid parameter vector never gets
a ChannelId. Real signatures are still a placeholder string (`sig`); M0 calls
for signature stubs only (see ROADMAP.md milestone M0).

Invariant (DESIGN.md section 9): this module must never import ucomm.attention.
AttentionClaim is data; its evaluation lives entirely on the receiver side.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .encoding import content_hash

ChannelId = str
EventHash = str
PubKey = str
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


# DESIGN.md section 3.3.
MEDIA_KINDS = frozenset({"text", "audio", "video", "file"})
WRITE_POLICIES = frozenset({"anyone", "members", "broadcaster"})
# DESIGN.md section 4 profile table.
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
    expected_duration_s: Optional[int] = None
    collateral: Optional[str] = None

    @property
    def claimed_priority(self) -> int:
        return self.importance + self.urgency


@dataclass(frozen=True)
class MediaDescriptor:
    mime: str
    size: Optional[int] = None
    codec: Optional[str] = None


@dataclass(frozen=True)
class Genesis:
    """Channel parameter vector, fixed at creation (DESIGN.md section 3.3).

    ChannelId = hash(canonical encoding of this record).
    """

    membership: Membership
    media: tuple[str, ...]  # subset of {"text","audio","video","file"}
    persistence: Persistence
    privacy: Privacy
    ordering: Ordering
    write_policy: str  # "anyone" | "members" | "broadcaster"
    rate_limit_per_epoch: Optional[int] = None
    suggested_priority_offset: int = 0  # advisory (DESIGN.md section 9)
    profile: Optional[str] = None  # blessed profile name, e.g. "chat" (DESIGN 4)
    nonce: str = ""

    def validate(self) -> None:
        """Raise GenesisError if this record's parameter vector is malformed.

        Not exhaustive cross-field policy (that's the profile conformance
        harness, issue K-8) — just the checks that must hold for *any*
        channel regardless of profile.
        """
        if not self.nonce:
            raise GenesisError(
                "nonce must be non-empty (distinguishes otherwise-identical "
                "channels; an empty nonce would let two unrelated channels "
                "with the same parameter vector collide on ChannelId)"
            )
        if not self.media:
            raise GenesisError("media must declare at least one kind")
        unknown_media = set(self.media) - MEDIA_KINDS
        if unknown_media:
            raise GenesisError(f"unknown media kind(s): {sorted(unknown_media)}")
        if self.write_policy not in WRITE_POLICIES:
            raise GenesisError(f"unknown write_policy: {self.write_policy!r}")
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
    media: Optional[MediaDescriptor] = None
    payload: Optional[SwarmRef] = None
    inline: Optional[bytes] = None
    attention: Optional[AttentionClaim] = None
    sig: str = ""  # TODO K-2: real signature over canonical bytes

    def event_hash(self) -> EventHash:
        return content_hash(self)

    def is_control_plane(self) -> bool:
        return self.kind in (
            EventKind.INVITATION,
            EventKind.RECEIPT,
            EventKind.CONTROL,
            EventKind.PRESENCE,
        )
