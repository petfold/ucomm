"""Real Swarm-backed author logs (M1).

Thin adapter from `RecordStoreAuthorLog` (`ucomm.store`) to recordstore's Bee
backends -- `BeeBytesStore` + `SwarmFeedPointer` -- instead of the in-memory
ones used for M0 prototyping. This is the "drop-in swap, not a rewrite"
ROADMAP.md promised: `RecordStoreAuthorLog` only ever needed a
`recordstore.RecordStore`; it never knew or cared whether that store was
backed by memory or a live Bee node.

Feeds need an IMMUTABLE postage batch (see CLAUDE.md, "Swarm facts to
respect"). This module never buys one -- pass an existing usable batch id
(`GET /stamps` on the target node), bought e.g. with
`POST /stamps/{amount}/{depth}?immutable=true` or swarmfs's `StampManager`.
"""

from __future__ import annotations

from recordstore import BeeBytesStore, RecordStore, SwarmFeedPointer

from .envelope import ChannelId, PubKey
from .signing import address_of
from .store import RecordStoreAuthorLog


def feed_topic(channel: ChannelId, author: PubKey) -> str:
    """Feed topic namespacing one author's per-channel log."""
    return f"ucomm/log/{channel}/{author}"


def open_author_feed_log(
    api_url: str, channel: ChannelId, *, signer_hex: str, postage_batch_id: str,
) -> tuple[RecordStore, RecordStoreAuthorLog]:
    """Open `signer_hex`'s own log for `channel`, backed by a real Swarm feed.

    `signer_hex` is the author's private key (hex); the feed owner (and
    hence `Envelope.author`, via `ucomm.signing.address_of`) is derived from
    it. Returns `(store, log)`: append through `log`, then call
    `store.commit()` to actually publish -- appends are staged locally until
    then, same as any other `RecordStore` (issue K-4's batching model, not a
    new one for Bee).
    """
    from bee.swarm.keys import PrivateKey

    author: PubKey = address_of(PrivateKey.from_hex(signer_hex))
    pointer = SwarmFeedPointer(
        api_url, feed_topic(channel, author),
        signer=signer_hex, postage_batch_id=postage_batch_id,
    )
    bytes_store = BeeBytesStore(api_url, postage_batch_id=postage_batch_id)
    store = RecordStore(bytes_store, pointer=pointer)
    return store, RecordStoreAuthorLog(store, channel, author)
