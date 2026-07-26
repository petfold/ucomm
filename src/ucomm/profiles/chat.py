"""Chat profile (DESIGN.md section 4; issue K-8, chat profile first).

The chat row of the profile table: 1:1 or closed N:M, interactivity 0-100,
permanent persistence, E2EE, standing (channel-level) invitation. This module
is the conformance test harness's first customer — `validate_chat_genesis`
is the check a chat app's genesis must pass, and `ChatChannel` is a minimal
end-to-end exercise of the kernel (genesis validation, per-author logs,
causal-DAG merge) with no network: everything here is in-process AuthorLogs.
Wiring a member's log to Swarm feeds (M1) or recordstore (`RecordStoreAuthorLog`,
already available) is a drop-in swap, not a rewrite of this module.
"""

from __future__ import annotations

from ..envelope import (
    Envelope,
    EventHash,
    EventKind,
    Genesis,
    GenesisError,
    MediaKind,
    Membership,
    Ordering,
    Persistence,
    Privacy,
    PubKey,
    WritePolicy,
)
from ..log import AuthorLog, merge_causal


def chat_genesis(nonce: str, rate_limit_per_epoch: int | None = None) -> Genesis:
    """Construct a genesis satisfying the chat profile; nonce distinguishes channels."""
    return Genesis(
        membership=Membership.INVITE, media=(MediaKind.TEXT,),
        persistence=Persistence.PERMANENT, privacy=Privacy.E2EE,
        ordering=Ordering.CAUSAL_DAG, write_policy=WritePolicy.MEMBERS,
        rate_limit_per_epoch=rate_limit_per_epoch, profile="chat", nonce=nonce,
    )


def validate_chat_genesis(genesis: Genesis) -> None:
    """Raise GenesisError unless `genesis` conforms to the chat profile row."""
    genesis.validate()
    if genesis.profile != "chat":
        raise GenesisError(f"not a chat-profile genesis: profile={genesis.profile!r}")
    if genesis.membership not in (Membership.INVITE, Membership.FIXED):
        raise GenesisError(
            f"chat profile requires invite or fixed membership, got {genesis.membership}"
        )
    if genesis.persistence != Persistence.PERMANENT:
        raise GenesisError("chat profile requires permanent persistence")
    if genesis.privacy != Privacy.E2EE:
        raise GenesisError("chat profile requires E2EE privacy")
    if genesis.ordering != Ordering.CAUSAL_DAG:
        raise GenesisError("chat profile requires causal-DAG ordering")
    if genesis.write_policy != WritePolicy.MEMBERS:
        raise GenesisError("chat profile requires write_policy=members")


class ChatChannel:
    """A two-party or closed-group chat, held as in-process per-author logs.

    Messages form a single causal chain: each send references the previous
    message across all members, so `messages()` (a `merge_causal` call) always
    returns send order. A real deployment has members polling each other's
    feeds and racing to append, hence genuinely concurrent tips and ties
    broken by `merge_causal`'s hash order — `ucomm.log`'s property tests
    already cover that; this class only needs to feed it real data.
    """

    def __init__(self, genesis: Genesis, members: tuple[PubKey, ...]) -> None:
        validate_chat_genesis(genesis)
        if not members:
            raise ValueError("a channel needs at least one member")
        self.genesis = genesis
        self.channel = genesis.channel_id()
        self.members = members
        self._logs: dict[PubKey, AuthorLog] = {m: AuthorLog() for m in members}
        self._next_seq: dict[PubKey, int] = {m: 1 for m in members}
        self._tip: tuple[EventHash, ...] = ()

    def send(self, author: PubKey, text: str) -> Envelope:
        if author not in self._logs:
            raise ValueError(f"{author!r} is not a member of this channel")
        env = Envelope(
            channel=self.channel, author=author, seq=self._next_seq[author],
            kind=EventKind.MESSAGE, refs=self._tip, inline=text.encode("utf-8"),
        )
        self._logs[author].append(env)
        self._next_seq[author] += 1
        self._tip = (env.event_hash(),)
        return env

    def messages(self) -> list[Envelope]:
        all_events = [env for log in self._logs.values() for env in log]
        return merge_causal(all_events)
