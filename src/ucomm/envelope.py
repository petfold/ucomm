"""Channel kernel schema: envelope and genesis records (M0 draft).

See docs/DESIGN.md sections 3.2-3.3. Canonical byte encoding lives in
`ucomm.encoding`, aligned with recordstore's format (issue K-1, done). Real
signatures are still absent (issue K-2); `sig` is a placeholder string.

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

    def channel_id(self) -> ChannelId:
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
