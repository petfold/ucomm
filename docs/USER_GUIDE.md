# ucomm user guide

A hands-on tour of `ucomm` as it stands today (milestones M0 and M1 —
see `docs/ROADMAP.md`): the channel kernel, real signing, a working chat profile,
the attention/policy engine, out-of-band contact exchange, and persistence
either in memory or on a real Swarm feed. Every code block below has
actually been run against the current code; the outputs shown are real,
just trimmed where a hash would otherwise take up a full line.

If you want the architecture and the reasoning behind it, read
`docs/DESIGN.md` and `docs/ATTENTION.md`. This guide is the "just show me
it working" companion.

## 1. Prerequisites

- Python ≥ 3.11
- `git`
- Internet access to PyPI, to install two small published dependencies
  (`recordstore`, `swarm-bee`) — both are real packages this project depends
  on, not local-only tools.
- Nothing else is required for anything in sections 2–12 below: no Swarm
  node, no funds, no network calls except the one-time `pip install`.
  Section 13 (real Swarm feed I/O) is the one part that needs a live Bee
  node and, to *write*, a funded postage batch — that section explains
  exactly what that means before you touch it.

## 2. Install

```bash
git clone https://github.com/petfold/ucomm.git
cd ucomm
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

This installs `ucomm` itself in editable mode, its runtime dependencies
(`recordstore` with its `bee` extra, `swarm-bee`), and the dev tools
(`pytest`, `hypothesis`, `mypy`, `ruff`).

## 3. Verify the install

```bash
pytest -q
```

Expected: all tests pass except one skip —

```
.......s................................................................ [100%]
71 passed, 1 skipped in 1.5s
```

The skip is `tests/test_bee_live.py`, which only runs against a real Bee
node (section 13). Everything else is fully offline.

Two more checks worth knowing about, both clean on a fresh checkout:

```bash
mypy src        # strict type checking
ruff check src tests   # linting
```

## 4. Concepts in 60 seconds

- A **channel** is a set of per-author append-only logs, a merge rule, and
  a parameter vector fixed at creation (the **genesis** record). The
  genesis's hash *is* the channel's id.
- Every event on a channel — a message, an invitation, a receipt — is one
  **envelope**: `channel`, `author`, `seq`, `kind`, optional `refs` (causal
  parents), a payload, and a `sig`.
- **Receiver sovereignty**: anything a sender declares (priority, offsets,
  importance) is advisory. The receiver's local policy engine is the only
  authority over what actually interrupts them.
- A **profile** (like "chat") is a named, tested bundle of genesis
  parameters — apps claim a profile instead of inventing free-form
  parameter combinations.

With that, here's all of it working.

## 5. Build a channel: genesis and ChannelId

```python
from ucomm.envelope import (
    Genesis, GenesisError, Membership, MediaKind, Persistence, Privacy,
    Ordering, WritePolicy,
)

genesis = Genesis(
    membership=Membership.INVITE,
    media=(MediaKind.TEXT,),
    persistence=Persistence.PERMANENT,
    privacy=Privacy.E2EE,
    ordering=Ordering.CAUSAL_DAG,
    write_policy=WritePolicy.MEMBERS,
    profile="chat",
    nonce="alice-and-bob-2026-07-26",   # anything unique to this channel
)
channel_id = genesis.channel_id()
print(channel_id)
# cba7a8744da9c4f0ac9e6d0400877ceb7d582f163955597fc755b40faa39c6f7
```

`channel_id()` validates the genesis before hashing it, so a malformed one
never gets an id:

```python
Genesis(
    membership=Membership.INVITE, media=(), persistence=Persistence.PERMANENT,
    privacy=Privacy.E2EE, ordering=Ordering.CAUSAL_DAG,
    write_policy=WritePolicy.MEMBERS, nonce="x",
).channel_id()
# raises GenesisError: media must declare at least one kind
```

The `nonce` is what makes two channels with an otherwise-identical
parameter vector distinct — always give it something unique (a random
string, a timestamp, whatever). Two calls with the same nonce and fields
produce the same `channel_id`; that's the point — it's a pure function of
the genesis's content, not a random UUID.

## 6. Envelopes and content hashing

```python
from ucomm.envelope import Envelope, EventKind

env = Envelope(
    channel=channel_id, author="placeholder", seq=1,
    kind=EventKind.MESSAGE, inline=b"hello",
)
print(env.event_hash())
# b15043233bdd9ea88d402ebdd78817b70199fe0a271e6033971d6d4aff33f362
```

`event_hash()` and `channel_id()` both go through `ucomm.encoding`'s
canonical byte encoding (sorted keys, compact separators — matching
`recordstore`'s format), so equal content always hashes identically
regardless of field order or which process computed it.

## 7. Real signing

`author` above was a placeholder — in practice it's an address derived
from a real secp256k1 key, and every envelope is actually signed:

```python
from bee.swarm.keys import PrivateKey
from ucomm.signing import address_of, sign_envelope, verify_envelope
from dataclasses import replace

alice_key = PrivateKey.from_hex("11" * 32)   # never hardcode a real key like this!
alice = address_of(alice_key)
print(alice)
# 19e7e376e7c213b7e7e7e46cc70a5dd086daff2a

unsigned = Envelope(
    channel=channel_id, author=alice, seq=1,
    kind=EventKind.MESSAGE, inline=b"hi bob",
)
signed = sign_envelope(unsigned, alice_key)
print(verify_envelope(signed))
# True

tampered = replace(signed, inline=b"hi mallory")
print(verify_envelope(tampered))
# False
```

This is secp256k1 with the same Ethereum signed-message digest Bee itself
verifies SOC/feed signatures against (via the `swarm-bee` package) — not a
second, ucomm-specific crypto scheme. `author`/`PubKey` is the signer's
*address*, not a raw public key; recoverable ECDSA signatures make that
enough to verify.

In a real app, generate keys randomly and keep them secret:

```python
import os
from bee.swarm.keys import PrivateKey

my_key = PrivateKey(os.urandom(32))
```

## 8. Per-author logs and deterministic merge

```python
from ucomm.log import AuthorLog, merge_causal

log = AuthorLog()
log.append(signed)
print(len(log))
# 1

merged = merge_causal(list(log))
```

`merge_causal` topologically sorts events by their `refs` (causal parents),
breaking ties between concurrent events by hash order — so two readers who
have collected the same set of events always converge on the same order,
no matter what order they received them in or how many times an event was
delivered twice.

## 9. The chat profile, end to end

This is the flagship demo: a real two-party chat, with real signing, real
verification on every read, and synced read-state receipts — no network
involved yet (that's section 13).

```python
from ucomm.profiles.chat import ChatChannel, chat_genesis

bob_key = PrivateKey.from_hex("22" * 32)
bob = address_of(bob_key)

chat_gen = chat_genesis(nonce="alice-and-bob-2026-07-26")
channel = ChatChannel(chat_gen, keys=(alice_key, bob_key))

channel.send(alice, "hey bob, are we still on for tomorrow?")
channel.send(bob, "yep! what time works for you?")
last = channel.send(alice, "how about 3pm?")
channel.mark_read(bob, last)

for msg in channel.messages():
    who = "alice" if msg.author == alice else "bob"
    print(f"{who}: {msg.inline.decode()}")
# alice: hey bob, are we still on for tomorrow?
# bob: yep! what time works for you?
# alice: how about 3pm?

print(channel.read_state())
# {'1563915e...': '9c168a15...'}   # bob's address -> the last event he's read
```

A few things worth noticing:

- `ChatChannel` takes real `PrivateKey`s, not bare address strings. Every
  `send()` signs; `messages()` verifies every event before returning
  anything, and raises `InvalidSignature` if any event has been tampered
  with — integrity isn't assumed, it's checked on every read.
- `chat_genesis()` builds a genesis that's guaranteed to pass
  `validate_chat_genesis()` — the conformance check for the chat profile
  row (permanent, E2EE, causal-DAG, standing invitation). Constructing a
  `Genesis` by hand with the wrong parameters and trying to use it as a
  `ChatChannel` raises `GenesisError` before anything is sent.
- `mark_read` writes a `RECEIPT` envelope on the *same* causal chain as
  messages, but `messages()` filters to `MESSAGE` kind only — receipts
  never show up as chat content, only in `read_state()`.
- Everything here lives in an in-process `AuthorLog` per member. Section
  12 shows the same shape of object (`RecordStoreAuthorLog`) persisted,
  and section 13 shows it backed by a real Swarm feed.

## 10. The attention / policy engine

Separately from any channel, `ucomm.attention` decides how loudly an
*invitation* (an envelope carrying an `AttentionClaim`) should interrupt
you, given your own local policy — never the sender's say-so.

```python
from ucomm.attention import PolicyState, SenderContext, decide, Intensity
from ucomm.envelope import AttentionClaim, TimeWindow

NOW = 1_000_000.0
policy = PolicyState(threshold=20)
known = SenderContext(known_contact=True)

smoke_from_house = Envelope(
    channel=channel_id, author=alice, seq=1, kind=EventKind.INVITATION,
    attention=AttentionClaim(
        importance=30, urgency=30,
        relevance=TimeWindow(start=NOW - 10, end=NOW + 3600),
    ),
)
print(decide(smoke_from_house, known, policy, NOW))
# Decision(intensity=<Intensity.FULL: 3>, effective_priority=40, residual=20, ceiling_applied=40)

tennis_schedule = Envelope(
    channel=channel_id, author=alice, seq=2, kind=EventKind.INVITATION,
    attention=AttentionClaim(
        importance=2, urgency=2,
        relevance=TimeWindow(start=NOW - 10, end=NOW + 3600),
    ),
)
print(decide(tennis_schedule, known, policy, NOW))
# Decision(intensity=<Intensity.FILED: 0>, effective_priority=4, residual=-16, ceiling_applied=40)
```

Both examples come straight from Attila Lendvai's canonical cases
(`docs/ATTENTION.md`): urgent-and-important breaks through, low-and-low gets
silently filed to a dashboard history with no interruption at all. `decide`
is a pure function of `(envelope, sender context, policy state, clock)` —
same inputs, same `Decision`, always; all the mutable state (ceilings,
offsets, thresholds) lives in `PolicyState`, which you own.

## 11. Out-of-band contact exchange

Before any channel exists, `ContactCard` lets you hand someone an address
they can verify actually corresponds to a key someone controls — useful
over a transport with no integrity guarantee of its own (paste, email, a
QR code).

```python
from ucomm.contact import make_contact_card, verify_contact_card, ContactCard

card = make_contact_card(alice_key)
print(card.to_str())
# ucomm-contact-v1:19e7e376e7c213b7e7e7e46cc70a5dd086daff2a:5a7b223c...

print(verify_contact_card(card))
# True

# On the receiving end, after pasting/scanning the string back in:
restored = ContactCard.from_str(card.to_str())
print(verify_contact_card(restored))
# True
```

The signature is domain-separated from envelope signing, so a contact card
can never be replayed as an envelope signature or vice versa. It proves
control of the address, not who the person is — matching a name to it is a
local petname decision, never something the card itself asserts.

## 12. Persistence: recordstore-backed logs (still offline)

`RecordStoreAuthorLog` gives the same log interface as `AuthorLog`, but
backed by `recordstore` — meaning it can survive a process restart, and
(section 13) can be pointed at a real Swarm feed with no code changes.
This example uses `recordstore`'s in-memory backend, so it's still fully
offline:

```python
from recordstore import RecordStore, MemoryBytesStore
from ucomm.store import RecordStoreAuthorLog

store = RecordStore(MemoryBytesStore())
alice_log = RecordStoreAuthorLog(store, channel_id, alice)
alice_log.append(signed)
root = store.commit()          # nothing is durable until you commit

# Simulate a fresh process opening the same store at the same root:
reopened = RecordStore.at(root, store._blobs)
reopened_log = RecordStoreAuthorLog(reopened, channel_id, alice)
print(list(reopened_log) == [signed])
# True
```

## 13. Optional: real Swarm feed I/O

This section needs a Bee node you can reach over HTTP, and, to publish
anything, a **funded, usable, immutable postage batch** on it. Read this
whole section before running anything — buying a batch spends real money
if the node is on mainnet.

**Before you do anything else, find out what network the node is actually
on:**

```bash
curl -s http://localhost:1633/wallet
```

Look at `chainID` in the response. `100` is **Gnosis Chain mainnet** — real
funds. If you don't recognize the chain id, or the wallet has a balance you
didn't expect, stop and check with whoever runs the node before spending
anything. Reads cost nothing; only *writing* (which needs a batch) spends.

If the node has no usable batch (`curl -s http://localhost:1633/stamps`
shows `{"stamps": []}` or nothing usable), you need one before you can
write. Buying one is a deliberate, explicit action — not something to
script blindly:

```bash
# Check current price/validity first -- currentPrice moves over time, so
# don't reuse a number from an old run of this guide:
curl -s http://localhost:1633/chainstate
# {"currentPrice": <price>, "minimumValidityBlocks": <floor>, ...}

# amount = blocks * currentPrice, with blocks comfortably above the floor
# (the purchase is rejected if it's too close to the minimum by the time
# the tx confirms). depth 17 is Bee's practical minimum for a small test.
# immutable=true matters: feeds need immutable stamps (CLAUDE.md's "Swarm
# facts to respect"). This bought a real batch for ~0.016 BZZ on 2026-07-26
# with price 68397 and a 18000-block window -- recompute, don't reuse.
curl -s -X POST "http://localhost:1633/stamps/<amount>/17?immutable=true&label=my-test"
# {"batchID": "...", "txHash": "..."}

# Poll until usable (can take ~30-60s for the purchase tx to confirm):
curl -s http://localhost:1633/stamps/<batchID>
```

(If you have `swarmfs` installed, `swarmfs.stamps.StampManager.plan()` /
`.buy()` compute and execute this for you, with the same "plan first, spend
only when you call `.buy()`" separation -- convenient, but not a `ucomm`
dependency, so not assumed here.)

With a usable batch id in hand, `ucomm.bee` wires a real log straight onto
a Swarm feed — the exact same `RecordStoreAuthorLog` interface as section
12, just backed by the network instead of memory:

```python
import os
from ucomm.bee import open_author_feed_log

api_url = "http://localhost:1633"
batch_id = "<your usable batch id>"
channel = "my-test-channel-" + os.urandom(4).hex()
key = PrivateKey(os.urandom(32))
author = address_of(key)

store, log = open_author_feed_log(
    api_url, channel, signer_hex=key.to_hex(), postage_batch_id=batch_id,
)

unsigned = Envelope(channel=channel, author=author, seq=1,
                     kind=EventKind.MESSAGE, inline=b"hello swarm")
log.append(sign_envelope(unsigned, key))
store.commit()      # this is the network write

# A different process, reading the same feed cold:
_reopened_store, reopened_log = open_author_feed_log(
    api_url, channel, signer_hex=key.to_hex(), postage_batch_id=batch_id,
)
print(list(reopened_log))   # the same signed envelope, read back from Swarm
```

This exact flow is what `tests/test_bee_live.py` runs and asserts on. To
run it yourself once you have a node and a batch:

```bash
UCOMM_BEE_API_URL=http://localhost:1633 \
UCOMM_BEE_POSTAGE_BATCH_ID=<your batch id> \
pytest tests/test_bee_live.py -v
```

It's skipped automatically if those environment variables aren't set,
which is why the normal `pytest` run in section 3 doesn't touch the
network at all.

## 14. Development workflow

```bash
pytest -q               # full offline suite
mypy src                 # strict type checking, must be clean
ruff check src tests     # linting; `--fix` for the auto-fixable ones
```

All three are clean on `main`. If you're adding something, keep them that
way — CI-equivalent hygiene, even though there's no CI configured yet.

## 15. Where to go next

- `docs/DESIGN.md` — the full architecture: two planes, the channel kernel,
  profiles, transports, identity, encryption.
- `docs/ATTENTION.md` — the priority algebra and policy engine in depth,
  plus the incentive mechanisms (bonds, reputation) not yet built.
- `docs/ROADMAP.md` — module map, milestones, and the open issue list. M0
  and M1 are done; M2 (notification daemon, universal inbox, first
  bridges) is next.
- `CLAUDE.md` — the invariants this codebase won't violate without a
  design discussion first, and the current-state summary kept in sync with
  every change.
