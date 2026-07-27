"""Push/hint delivery abstraction (issue D-4).

DESIGN.md section 5: PSS's actual job is narrow -- "something changed on
this channel, maybe look sooner" -- not content delivery. A hint is
advisory and swappable per CLAUDE.md invariant 7: losing every hint ever
costs latency, never correctness. `ucomm.daemon.build_dashboard` and
`directory_read_state` work by polling `channel_events` directly and don't
consult a `HintSource` at all -- this module exists so a real backend (Bee
PSS, native GSOC pub/sub once it lands, or an off-Swarm relay like ntfy)
can be wired in later without any of D-1..D-3 changing, and so none of
them can quietly become required. There is deliberately no "block until a
hint arrives" method here, only "drain what you have" -- a `HintSource`
that never has anything is a valid, fully-functional implementation
(poll-only), not a degraded one.

Same shape as `Rendezvous` (issue K-5): an interface plus the one
implementation this issue ships, in-memory, for tests. A Bee-PSS-backed
implementation, a GSOC-pub/sub-backed one, and an off-Swarm one are all
future, separate work -- deliberately not decided here (invariant 7: don't
pick a backend early just because it's the only one built).
"""

from __future__ import annotations

from typing import Protocol

from .envelope import ChannelId


class HintSink(Protocol):
    """Where a "channel X changed" hint gets published to."""

    def publish(self, channel: ChannelId) -> None:
        """Signal that `channel` may have new content. No delivery guarantee."""
        ...


class HintSource(Protocol):
    """Where a daemon drains pending hints from. Never blocks."""

    def poll(self) -> list[ChannelId]:
        """Return and clear channels hinted since the last poll, if any."""
        ...


class InMemoryHints:
    """Process-local hint queue -- tests, and the only implementation this
    issue ships.

    A hinted channel is deduplicated: repeated hints for the same channel
    collapse into one "look at this" signal, not a counter, since a hint
    carries no information beyond "something happened here."
    """

    def __init__(self) -> None:
        self._pending: set[ChannelId] = set()

    def publish(self, channel: ChannelId) -> None:
        self._pending.add(channel)

    def poll(self) -> list[ChannelId]:
        drained = sorted(self._pending)
        self._pending = set()
        return drained
