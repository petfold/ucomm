"""Chat profile (DESIGN.md section 4; issue K-8, chat profile first).

The chat row of the profile table: 1:1 or closed N:M, interactivity 0-100,
permanent persistence, E2EE, standing (channel-level) invitation. This module
is the conformance test harness's first customer — `validate_chat_genesis`
is the check a chat app's genesis must pass, and `ChatChannel` is a minimal
end-to-end exercise of the kernel (genesis validation, per-author logs,
causal-DAG merge, real signing) with no network: everything here is
in-process `AuthorLog`s. Wiring a member's log to Swarm feeds (M1) or
recordstore (`RecordStoreAuthorLog`, already available) is a drop-in swap,
not a rewrite of this module.
"""

from __future__ import annotations

from bee.swarm.keys import PrivateKey

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
from ..signing import InvalidSignature, address_of, sign_envelope, verify_envelope


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

    Members are given as `PrivateKey`s, not bare addresses: every message is
    really signed (`ucomm.signing.sign_envelope`) and every read really
    verifies (`verify_envelope`), so a corrupted or forged event is caught
    before it reaches `messages()` rather than assumed away. `Envelope.author`
    is still the address (`address_of(key)`), matching how Bee identifies
    feed/SOC owners.

    Messages and receipts share one causal chain: every append (`send` or
    `mark_read`) references the previous event across all members, so
    `messages()`/`read_state()` (both `merge_causal` calls) always return
    send order. A real deployment has members polling each other's feeds and
    racing to append, hence genuinely concurrent tips and ties broken by
    `merge_causal`'s hash order — `ucomm.log`'s property tests already cover
    that; this class only needs to feed it real data.
    """

    def __init__(self, genesis: Genesis, keys: tuple[PrivateKey, ...]) -> None:
        validate_chat_genesis(genesis)
        if not keys:
            raise ValueError("a channel needs at least one member")
        self.genesis = genesis
        self.channel = genesis.channel_id()
        self._keys: dict[PubKey, PrivateKey] = {address_of(k): k for k in keys}
        self.members: tuple[PubKey, ...] = tuple(self._keys)
        self._logs: dict[PubKey, AuthorLog] = {m: AuthorLog() for m in self.members}
        self._next_seq: dict[PubKey, int] = {m: 1 for m in self.members}
        self._tip: tuple[EventHash, ...] = ()

    def send(self, author: PubKey, text: str) -> Envelope:
        if author not in self._keys:
            raise ValueError(f"{author!r} is not a member of this channel")
        return self._append(author, EventKind.MESSAGE, inline=text.encode("utf-8"))

    def mark_read(self, reader: PubKey, through: Envelope) -> Envelope:
        """Record that `reader` has read up through `through` (inclusive).

        DESIGN.md section 10: "read-state is a synced event kind" -- a
        RECEIPT envelope like any other, so it syncs the same way messages
        do. The acknowledged event's hash is a small inline pointer, not
        channel content (CLAUDE.md invariant 3, two planes); `refs` stays
        reserved for causal-DAG ordering, same as every other event here.
        """
        if reader not in self._keys:
            raise ValueError(f"{reader!r} is not a member of this channel")
        acked = through.event_hash().encode("ascii")
        return self._append(reader, EventKind.RECEIPT, inline=acked)

    def _append(self, author: PubKey, kind: EventKind, *, inline: bytes) -> Envelope:
        unsigned = Envelope(
            channel=self.channel, author=author, seq=self._next_seq[author],
            kind=kind, refs=self._tip, inline=inline,
        )
        env = sign_envelope(unsigned, self._keys[author])
        self._logs[author].append(env)
        self._next_seq[author] += 1
        self._tip = (env.event_hash(),)
        return env

    def _verified_events(self) -> list[Envelope]:
        all_events = [env for log in self._logs.values() for env in log]
        merged = merge_causal(all_events)
        for env in merged:
            if not verify_envelope(env):
                raise InvalidSignature(f"invalid signature on event from {env.author!r}")
        return merged

    def messages(self) -> list[Envelope]:
        return [env for env in self._verified_events() if env.kind is EventKind.MESSAGE]

    def read_state(self) -> dict[PubKey, EventHash]:
        """Latest event hash each member has acknowledged (last receipt wins)."""
        state: dict[PubKey, EventHash] = {}
        for env in self._verified_events():
            if env.kind is EventKind.RECEIPT and env.inline is not None:
                state[env.author] = env.inline.decode("ascii")
        return state
