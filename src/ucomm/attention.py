"""Attention layer: priority algebra and policy engine (ATTENTION.md).

Pure and deterministic by design: decide(envelope, policy, now) -> Decision is a
function of its arguments only. All mutable state (ceilings, offsets, thresholds,
reputation ratchet) lives in PolicyState, owned by the daemon.

Receiver sovereignty: this module consumes AttentionClaim data and never
constructs envelopes. One-way dependency: attention -> envelope, never reverse.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum

from .envelope import Envelope, EventKind, PubKey


class Intensity(IntEnum):
    """Graded notification output (ATTENTION.md section 3)."""

    FILED = 0        # silently filed; dashboard history only
    BADGE = 1        # badge / dashboard, no interruption
    SOFT = 2         # ring once / vibrate only
    FULL = 3         # full alert
    BREAKTHROUGH = 4 # overrides DND


# Residual thresholds for grading, in log-scale priority units.
SOFT_BAND = 5          # |residual| <= SOFT_BAND counts as "near threshold"
BREAKTHROUGH_MARGIN = 20


@dataclass(frozen=True)
class PolicyState:
    """Receiver-local policy snapshot. Never published, never negotiated."""

    threshold: int  # current global threshold; DND = high value
    default_ceiling_known: int = 40
    default_ceiling_stranger: int = 0
    wot_ceiling_slope: int = 10  # ceiling = base - slope * wot_distance (ATTENTION 5)
    contact_ceilings: Mapping[PubKey, int] = field(default_factory=dict)
    channel_offsets: Mapping[str, int] = field(default_factory=dict)
    endpoint_offset: int = 0  # e.g. raised while in an interactive session
    bond_credit: int = 10  # credibility bonus when valid collateral attached


@dataclass(frozen=True)
class SenderContext:
    """What the receiver knows about the sender (from identity/WoT + recsys)."""

    known_contact: bool
    wot_distance: int | None = None  # None = no path
    recsys_prior: int = 0  # advisory prior from RECOMMENDATION.md section 6
    collateral_valid: bool = False


@dataclass(frozen=True)
class Decision:
    intensity: Intensity
    effective_priority: int
    residual: int
    ceiling_applied: int


def ceiling_for(sender: PubKey, ctx: SenderContext, policy: PolicyState) -> int:
    """Per-sender priority ceiling (ATTENTION.md sections 2, 5)."""
    if sender in policy.contact_ceilings:
        return policy.contact_ceilings[sender]
    if ctx.known_contact:
        return policy.default_ceiling_known
    if ctx.wot_distance is not None:
        base = policy.default_ceiling_known
        return max(
            policy.default_ceiling_stranger,
            base - policy.wot_ceiling_slope * ctx.wot_distance + ctx.recsys_prior,
        )
    return policy.default_ceiling_stranger + ctx.recsys_prior


def decide(env: Envelope, ctx: SenderContext, policy: PolicyState, now: float) -> Decision:
    """Map one control-plane envelope to a graded notification intensity.

    Pure function: (envelope, sender context, policy state, clock) -> Decision.
    """
    if env.kind is not EventKind.INVITATION or env.attention is None:
        return Decision(Intensity.FILED, 0, -(10**6), 0)

    claim = env.attention
    if not claim.relevance.active(now):
        return Decision(Intensity.FILED, 0, -(10**6), 0)  # expired -> timeline

    cap = ceiling_for(env.author, ctx, policy)
    credibility = policy.bond_credit if ctx.collateral_valid else 0

    effective = (
        min(claim.claimed_priority, cap)
        + policy.channel_offsets.get(env.channel, 0)
        + policy.endpoint_offset
        + credibility
    )
    residual = effective - policy.threshold

    if residual > BREAKTHROUGH_MARGIN:
        intensity = Intensity.BREAKTHROUGH
    elif residual > SOFT_BAND:
        intensity = Intensity.FULL
    elif residual > 0:
        intensity = Intensity.SOFT
    elif residual > -SOFT_BAND:
        intensity = Intensity.BADGE
    else:
        intensity = Intensity.FILED

    return Decision(intensity, effective, residual, cap)
