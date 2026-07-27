"""Notification daemon core: channel directory + graded dashboard (M2).

DESIGN.md section 10: the user keeps a private channel directory (every
channel they participate in, across all apps, with local per-channel policy
overrides); one notification daemon per device computes effective priority
over it and emits a graded dashboard -- active requests ordered by priority
(including sub-threshold ones, silently filed), plus an obsolete timeline for
expired ones.

Resolves the open question in DESIGN.md section 12: the dashboard is a
projection, not authoritative state. `build_dashboard` is a pure function of
(directory, channel events, policy, sender contexts, clock) -- like
`ucomm.attention.decide`, its output is never stored, only recomputed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from .attention import Decision, PolicyState, SenderContext, decide
from .envelope import ChannelId, Envelope, EventHash, EventKind, PubKey
from .log import merge_causal, read_state


@dataclass(frozen=True)
class DirectoryEntry:
    """One participated channel, with local-only policy overrides.

    Mute is a large negative `channel_offset`, not a separate mechanism
    (ATTENTION.md section 2 / DESIGN.md section 11) -- so there's no
    `muted` field here to duplicate it.
    """

    channel: ChannelId
    profile: str | None = None
    channel_offset: int = 0


class ChannelDirectory:
    """Every channel the user participates in, across all apps (DESIGN.md
    section 10). Purely local and private: never signed, never synced --
    unlike the channels it lists, the directory itself has no merge rule,
    because there's exactly one writer, the local user.
    """

    def __init__(self) -> None:
        self._entries: dict[ChannelId, DirectoryEntry] = {}

    def add(self, entry: DirectoryEntry) -> None:
        self._entries[entry.channel] = entry

    def remove(self, channel: ChannelId) -> None:
        self._entries.pop(channel, None)

    def __iter__(self) -> Iterator[DirectoryEntry]:
        return iter(self._entries.values())

    def __contains__(self, channel: ChannelId) -> bool:
        return channel in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def channel_offsets(self) -> dict[ChannelId, int]:
        """Directory-derived offsets, ready to merge into a `PolicyState`."""
        return {e.channel: e.channel_offset for e in self._entries.values()}


@dataclass(frozen=True)
class DashboardItem:
    channel: ChannelId
    envelope: Envelope
    decision: Decision


@dataclass(frozen=True)
class Dashboard:
    """A graded view over active/obsolete attention requests -- a
    projection, never persisted (DESIGN.md section 12)."""

    active: tuple[DashboardItem, ...]    # relevance still active; sorted by
                                          # effective_priority, highest first
    obsolete: tuple[DashboardItem, ...]  # relevance window has passed


def build_dashboard(
    directory: ChannelDirectory,
    channel_events: Mapping[ChannelId, Iterable[Envelope]],
    policy: PolicyState,
    sender_contexts: Mapping[PubKey, SenderContext],
    now: float,
    *,
    default_sender_context: SenderContext | None = None,
) -> Dashboard:
    """Compute the dashboard fresh from current state.

    Never store the result -- call this again next time. It's cheap, and
    recomputing is the only way the dashboard can't drift from the channels
    and policy it's derived from (same discipline as `decide()` itself).

    Only `INVITATION` envelopes carrying an `AttentionClaim` are dashboard
    material -- ordinary messages aren't "requests" in DESIGN.md section 10's
    sense and are silently skipped, matching `decide()`'s own treatment of
    them (a trivial FILED sentinel) rather than cluttering the timeline.

    Callers pass unmerged events (e.g. every member's raw log); each
    channel's stream is merged internally, so a duplicate delivery or an
    event reachable through two members' logs is counted once, not twice.
    """
    unknown_ctx = default_sender_context or SenderContext(known_contact=False)
    active: list[DashboardItem] = []
    obsolete: list[DashboardItem] = []

    for entry in directory:
        for env in merge_causal(channel_events.get(entry.channel, ())):
            if env.kind is not EventKind.INVITATION or env.attention is None:
                continue
            ctx = sender_contexts.get(env.author, unknown_ctx)
            item = DashboardItem(entry.channel, env, decide(env, ctx, policy, now))
            if env.attention.relevance.active(now):
                active.append(item)
            else:
                obsolete.append(item)

    active.sort(key=lambda item: item.decision.effective_priority, reverse=True)
    return Dashboard(active=tuple(active), obsolete=tuple(obsolete))


def directory_read_state(
    directory: ChannelDirectory,
    channel_events: Mapping[ChannelId, Iterable[Envelope]],
) -> dict[ChannelId, dict[PubKey, EventHash]]:
    """Read-state (`ucomm.log.read_state`) for every channel in the
    directory, rolled up into one view (issue D-3).

    `ucomm.profiles.chat.ChatChannel.read_state` already does this for one
    channel; the daemon needs it across every channel a user is in,
    regardless of profile -- possible without profile-specific code because
    `RECEIPT`'s meaning (`ucomm.log.read_state`'s docstring) is a kernel
    convention, not a chat-profile one. Callers pass unmerged events; each
    channel's stream is merged internally so callers don't have to remember
    to do it themselves.
    """
    return {
        entry.channel: read_state(merge_causal(channel_events.get(entry.channel, ())))
        for entry in directory
    }
