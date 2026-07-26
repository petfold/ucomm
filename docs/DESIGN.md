# DESIGN — universal communicator middleware

Status: draft for discussion. Companion documents: ATTENTION.md (priority model
and mechanisms), RECOMMENDATION.md (discovery layer), ROADMAP.md (build plan).

## 1. Thesis and prior art

All person-to-person(s) communication apps are parameterizations of one object:
get media from one or more people to one or more people, subject to a policy on
attention. The differences — email vs. chat vs. calls vs. streams vs. social —
reduce to a small parameter vector (§4).

Evidence this works: **Nostr** — one tiny signed-event schema plus "kinds"
produced chat, social feeds, marketplaces, streaming, and publishing without
redesigning the substrate. Its weaknesses (relay centralization, no storage
guarantees, free-to-send spam) are precisely what Swarm's storage incentives and
postage economics fix.

The cautionary tale: **XMPP** — an extensible core whose extensions (XEPs)
fragmented until interop became nominal. The defense adopted here is a kernel
small enough to fit on a page, plus a small set of blessed **profiles** with
conformance tests (§4), instead of free-form parameter soups.

Other prior art deliberately borrowed from:
- Secure Scuttlebutt / Hypercore: per-author append-only logs as the unit of
  authority; a "place" is a set of logs plus a merge rule.
- Matrix: event DAG with causal references; state resolution scoped per channel.
- Waku: RLN rate-limiting nullifiers for spam resistance at open write points.
- MLS (RFC 9420): asynchronous group key management.
- Petname systems / Spritely: local naming, no global namespace.

## 2. The two-plane split

The single most important structural decision. Attila Lendvai's taxonomy phases
("1) request the recipient's attention, 2) deliver the payload") become two
protocol planes:

- **Control plane**: invitations, channel negotiation, receipts, presence,
  membership changes. Small, structured, priority-annotated envelopes. This is
  what the universal inbox and notification daemon consume.
- **Data plane**: payload delivery — text, audio, video, files. Pointers into
  Swarm content (or live transports) referenced from control/data events.

Legacy apps conflate the planes (a message *is* its own notification), which is
why notification policy is unportable across apps. Once the control plane is a
standard schema, the universal inbox is a query, not an integration project.

## 3. Channel kernel

### 3.1 Definition

> A **channel** is (a) a set of per-author append-only logs, (b) a merge rule,
> and (c) a parameter vector fixed in a genesis record.

Each participant writes only to their own single-owner log (their outbox for
that channel). Readers subscribe to all member logs and merge locally. There is
no shared-write state on the hot path — no consensus, no contention — which maps
exactly onto Swarm single-owner chunks and feeds. Multi-writer state appears
only at **rendezvous points** (§6), which is where GSOC lives.

The author-log layer is a versioned key → record stream; **recordstore** is the
natural persistence substrate (one record per chunk, deterministic encoding,
POT-indexed). ucomm should be a downstream consumer of recordstore, not a
parallel storage effort.

### 3.2 Envelope schema

Every event on any channel, both planes, is one envelope:

```
Envelope {
  channel:   ChannelId          # hash of the genesis record
  author:    PubKey             # device subkey, delegated from root identity
  seq:       u64                # per-author sequence number (log position)
  refs:      [EventHash]        # causal parents (DAG); empty if ordering=none
  kind:      EventKind          # message | invitation | receipt | control | presence
  media:     MediaDescriptor    # mime, size, codec hints
  payload:   SwarmRef | inline  # encrypted content, or pointer to it
  attention: Option<AttentionClaim>   # see ATTENTION.md; on invitations/first contact
  sig:       Signature
}
```

`AttentionClaim` carries claimed importance and urgency (log-scale), a relevance
time window after which the request self-expires, the requested interactivity
level (0–100, Attila's continuity-of-attention axis), expected duration, and
optional collateral (bond reference or stamp proof). All claim fields are
**advisory**; see receiver sovereignty (§9).

### 3.3 Genesis parameters

The genesis record (whose hash is the ChannelId) fixes:

| Parameter | Values |
|---|---|
| membership | fixed list \| invite-capability \| open |
| media set | subsets of {text, audio, video, file}; each independently deliverable |
| persistence | permanent \| ephemeral (crypto-shredding; see §8) \| archival-optional |
| privacy | public \| ACT-gated \| E2EE(scheme) |
| ordering | causal-DAG merge \| per-author independent \| moderator-sequenced |
| write policy | anyone \| members \| single broadcaster |
| rate limits | per-member message budget per epoch |
| priority offset | suggested (advisory) offset applied by subscribing clients |

### 3.4 Ordering and merge

Ordering is a channel parameter, not a global commitment:
- **causal-DAG**: events reference parents (`refs`); merge is a deterministic
  topological linearization with a tie-break (hash order). Chat, forums.
- **per-author independent**: no cross-author order needed. Social feeds,
  broadcasts.
- **moderator-sequenced**: a designated sequencer log establishes total order.
  Moderated rooms, auctions-over-channels later.

Richer CRDT semantics (collaborative documents) are out of scope for the kernel;
they live in payloads. The kernel guarantees only signed, causally-annotated,
per-author-ordered event delivery.

## 4. Profiles: apps as parameter settings

| Profile | Topology | Interactivity | Persistence | Privacy | Invitation granularity |
|---|---|---|---|---|---|
| mail | 1:few | 0 (async) | permanent | optional E2EE | per-message |
| chat | 1:1, N:M closed | 0–100 | permanent | E2EE | standing (channel-level accept) |
| call | 1:few | ~100 | ephemeral, opt. recording | E2EE | per-session, high urgency |
| open-band ("CB radio") | N:M open topic | ~100 | ephemeral | open | standing, low ceiling |
| broadcast (radio/music/video) | 1:N | live | optional archive | public | subscription |
| social | 1:N + reply graph | 0 | permanent | public or ACT | follow = standing accept, low ceiling |
| forum | N:M | 0 | permanent | member ACT | standing, per-thread offsets |

Observations that keep the model honest:
- A "follow" is a standing acceptance of a channel at a low priority ceiling.
- A phone call is an invitation with interactivity≈100 and a short relevance
  window; its recording is the *same channel* with persistence enabled.
- A reply/quote is an envelope whose `refs` cross channels (subject to the
  target's privacy).

**Profile discipline (anti-XMPP rule):** apps claim profiles, not ad-hoc
parameter combinations. Each profile ships a conformance test suite. New
profiles require a spec change, not a config file. The kernel never grows to
accommodate a profile; profiles compose kernel features only.

## 5. Transports

The interactivity axis is honest about what Swarm is: addressable persistence,
not packet delivery.

| Transport | Role | Constraints (from Bee 2.8.x) |
|---|---|---|
| **Feeds / single-owner chunks** | author logs, channel directories, profile state | immutable stamps required for feeds; content persists while stamps are funded |
| **GSOC** (Graffiti Single-Owner Chunks) | many-writers-to-one-address rendezvous: open mailboxes, group discovery, notification fan-in | subscriber must be a **full node** in the target neighborhood (mined identifier); use **mutable** stamps; pub/sub layer still in progress (V. Tóth, V. Trón) |
| **PSS** | point-to-point push (notification hints, signaling) | receiving node must be **full** to subscribe; targets capped at 4 hex chars in bee-js |
| **WebRTC** | interactive audio/video (interactivity ≳ 50) | signaling (SDP/ICE) carried as channel control events over Swarm; optional archival written back to the same channel log |

Light-client reality: phones will not run full nodes, so PSS/GSOC subscription
is delegated to a user-chosen full node (their own, a household node, or a paid
service) that forwards hints to devices. This "notification relay" is a trust
decision surfaced in the identity layer; it sees traffic metadata (which
encrypted channels are active), not content. Metadata minimization at the relay
is an open problem (ROADMAP, issue K-9).

## 6. Rendezvous

Everything among known contacts runs today on feeds + PSS: each party learns the
other's log addresses at contact exchange. Rendezvous is only needed for:

1. **Unsolicited first contact** — an open GSOC mailbox per identity, where
   strangers post contact-request envelopes. This is exactly where the spam
   economics of ATTENTION.md (postage floor, bonds, RLN) concentrate.
2. **Discovery of open channels/groups** — GSOC-backed topic registries.

Both sit behind a `Rendezvous` interface with three planned implementations:
in-memory (tests), PSS-based shim / static bootstrap (interim), GSOC (target).
This is what makes it sensible to build now rather than wait for GSOC to land.

## 7. Identity and web of trust (standalone library)

Per Attila's implementation note, independently useful components are standalone
libraries. Identity/WoT is the clearest case:

- Root keypair per person; **device subkeys** via signed delegation certificates
  (with expiry and revocation events published on the identity's own log).
- **Petnames** locally; no global namespace. Contact list stored private on
  Swarm (ACT or E2EE), synced across devices.
- **WoT edges** as optionally-published signed attestations ("I know this key,
  confidence c"). Consumed by the attention engine (default ceilings for
  strangers, ATTENTION.md §4) and the recommendation layer (neighborhood
  construction, RECOMMENDATION.md §3).
- Alignment target: the ecosystem "Swarm ID" work — track it, don't fork it.

## 8. Encryption and the honest tension

- 1:1: double ratchet.
- Groups: **MLS (RFC 9420)** — designed for asynchronous delivery, maps well to
  logs; epoch state carried as control events.
- Public-ish channels: **ACT** gating at the storage layer. Two ACT properties
  must be surfaced in UX, not hidden: losing the history reference is permanent
  loss of access, and **revocation is forward-only** (a removed grantee keeps
  whatever they could already read).
- "Ephemeral" on an immutable replicated network can only mean
  **crypto-shredding**: keys destroyed on schedule, ciphertext persists until
  stamps lapse. Forward secrecy holds (past keys deleted), but ephemerality is a
  key-lifecycle property, not a data-deletion guarantee. The spec says this
  plainly; apps must too.

## 9. Receiver sovereignty (normative principle)

Everything a sender or a channel declares — priority, offsets, importance,
suggested anything — is advisory. The protocol guarantees only that claims are
signed and optionally collateralized. The receiver's local policy engine is the
sole authority over the receiver's attention. No protocol message can force a
notification. This principle is load-bearing for the whole attention layer and
is enforced in code by keeping claim parsing and policy evaluation in separate
modules with a one-way dependency.

## 10. Universal inbox and notification daemon

- The user keeps a private **channel directory**: a log listing every channel
  they participate in, across all apps, with local per-channel policy overrides.
- One **notification daemon** per device subscribes (PSS hints via the relay,
  plus feed polling) to the control planes of everything in the directory,
  computes effective priority (ATTENTION.md §3), and emits **graded**
  notifications. Apps register as renderers for profiles; they never touch the
  OS notification system directly.
- **Read-state is a synced event kind**: receipts written to a personal state
  log, so reading in one client clears everywhere.
- **Relevance expiry is enforced**: expired invitations drop from the active
  dashboard to the obsolete timeline without ever demanding attention.
- The dashboard is Attila's: active requests ordered by effective priority
  (including sub-threshold calls, silently filed), plus a timeline of obsolete
  requests, filterable by initiator.

### Adoption wedge: the attention firewall

The daemon delivers value before any native app exists, given **bridges**:
adapters ingesting Matrix, Nostr, email (IMAP), and RSS into the same envelope
schema and policy engine. A personal attention firewall — unified inbox, one DND
policy with exceptions, across everything — is a product people would run for
its own sake. Come for the unified DND, stay for the protocol. This also fits
Swarm's middleware-not-destination positioning.

## 11. Risks

- **Inner-platform effect**: the configurable everything-communicator becomes as
  complex as the sum of the apps. Defenses: one-page kernel, profile discipline
  with conformance tests, middleware owns substrate + attention, apps own UX.
- **Full-node dependency** for PSS/GSOC subscription pushes casual users toward
  relays; relay trust and metadata leakage need explicit treatment.
- **GSOC pub/sub immaturity**: mitigated by the Rendezvous interface; also an
  opportunity — a concrete downstream consumer with stated requirements (write
  rates, mailbox spam economics, light-client needs) sharpens the protocol work.
- **Attention-claim gaming**: addressed head-on in ATTENTION.md; free-to-claim
  priority would be pinned at max by LLM spam within days.
