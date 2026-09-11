# ROADMAP — modules, milestones, initial issues

## Module decomposition (standalone where independently useful)

Per Attila's implementation note, components useful outside the communicator are
standalone libraries with their own repos once stable:

| Module | Scope | Depends on | Standalone? |
|---|---|---|---|
| `ucomm.envelope` | envelope + genesis schema, canonical encoding | — | eventually (schema lib) |
| `ucomm.encoding` | canonical byte encoding + content hashing (`ChannelId`/`EventHash`) | — | yes, alongside envelope |
| `ucomm.signing` | secp256k1 signing/verification (`sign_envelope`, `verify_envelope`) | envelope, `swarm-bee` | **yes** — a generic Bee-compatible envelope signer |
| `ucomm.contact` | out-of-band contact exchange (`ContactCard`) | signing | **yes** — generic address self-attestation |
| `ucomm.log` | per-author append-only channel logs | recordstore | no (thin adapter) |
| `ucomm.store` | recordstore adapter for author logs (`RecordStoreAuthorLog`) | recordstore | no (thin adapter) |
| `ucomm.bee` | real Swarm feed backend for `RecordStoreAuthorLog` | recordstore's Bee extra | no (thin adapter) |
| `ucomm.rendezvous` | `Rendezvous` interface; InMemory / PSS-shim / GSOC impls | Bee API | no |
| `ucomm.attention` | priority algebra + policy engine (pure functions + policy store) | envelope | **yes** — useful for any notification system |
| `ucomm.profiles.chat` | chat profile: conformance check + end-to-end `ChatChannel` | envelope, log, signing | no (profile, not standalone) |
| `identity-wot` | root keys, device delegation, petnames, attestations | Swarm feeds, ACT | **yes** — track Swarm ID work |
| `ucomm.daemon` | notification daemon: subscriptions, graded alerts, read-state sync, dashboard state | all above | no |
| `bridges/*` | Matrix, Nostr, IMAP, RSS → envelope adapters | envelope, daemon | per-bridge |
| `ucomm.recsys` | embeddings + open-signal CF + sketches + curation (RECOMMENDATION.md) | identity-wot, bridges, OntoDAG/mdl-fca | **yes** |
| `channel-directory` | curated closed-platform directory + WebSub ingester | Swarm feeds | **yes** — useful far beyond ucomm |
| `ucomm.rt` | WebRTC signaling profile (call setup over control plane) | envelope | no |

One-way dependency rule (receiver sovereignty, DESIGN.md §9): `envelope` never
imports `attention`; `attention` evaluates claims, never constructs them.

## Milestones

**M0 — schema + algebra (no network).**
Envelope/genesis dataclasses with canonical encoding and signature stubs;
priority algebra as pure functions; policy engine over an in-memory store;
InMemory rendezvous; property tests (determinism, additivity, ceiling
monotonicity). *Everything here is prototypable today; the src/ skeleton in
this repo is M0's starting point.*

**M1 — known-contact channels over Swarm.**
Author logs on feeds (via recordstore where it fits); contact exchange
(addresses + keys) out-of-band; two-party and small-group chat profile
end-to-end; read-state receipts synced. No GSOC needed.

- Real signing **done**: `ucomm.signing` (secp256k1 + Ethereum signed-message
  digest via `bee.swarm.keys`, the same scheme Bee verifies SOC/feed
  signatures against). `ChatChannel` now signs every send and verifies every
  read instead of leaving `sig` a placeholder.
- Read-state receipts **done**: `ChatChannel.mark_read`/`read_state` --
  RECEIPT envelopes on the same causal chain as messages, acknowledged event
  hash carried as a small `inline` pointer (not `refs`, which stays reserved
  for ordering; CLAUDE.md invariant 3). `messages()` filters to MESSAGE kind
  only, so this was additive -- no existing test changed.
- Author logs on real Swarm feeds **done**: `ucomm.bee.open_author_feed_log`
  wires `RecordStoreAuthorLog` to recordstore's `BeeBytesStore` +
  `SwarmFeedPointer` -- the "drop-in swap, not a rewrite" this promised,
  confirmed live against a Bee 2.8.1 node (2026-07-26): a signed envelope
  written through one process's log round-tripped, byte-identical and
  signature-valid, through a second process opening the same feed cold.
  `tests/test_bee_live.py` is opt-in (env-var gated; needs a reachable node
  and a funded immutable postage batch) and skipped by default.
- Out-of-band contact exchange **done**: `ucomm.contact.ContactCard` --
  a self-attested address (domain-separated signature, so it can't be
  replayed as or forged from an envelope signature), with a compact
  `to_str`/`from_str` form for pasting/QR codes. Deliberately not the
  identity-wot library (root keys, device delegation, petnames --
  standalone, tracks the ecosystem "Swarm ID" work): just proof of control
  of an address before a channel exists.
- **M1 is now feature-complete** per this milestone's description: real
  signing, receipts, real feed I/O, and contact exchange are all done; the
  chat profile itself is still only wired to in-process `AuthorLog`s (not
  `ucomm.bee`) -- swapping that in is mechanical, not a new milestone item.

**M2 — daemon + universal inbox + first bridges.**
Notification daemon with graded alerts and dashboard (active/obsolete);
channel directory; PSS hint path via a full node; IMAP and Nostr bridges —
the **attention firewall** as standalone value.

- Channel directory + graded dashboard **done** (D-1, D-2): `ucomm.daemon`.
  Read-state aggregation **done** (D-3). Hint-delivery interface **done**
  (D-4's abstraction; no real backend chosen yet, deliberately -- see D-4).
  IMAP bridge **done** (D-5, both layers: conversion + live fetch loop),
  though the live loop is only verified against a fake client so far, not
  a real mailbox. Wiring a real D-4 backend, running D-5's live loop
  against a real mailbox at least once, and the Nostr bridge (D-6) are
  what's left of M2.

**M3 — rendezvous + spam economics.**
GSOC mailboxes for unsolicited contact (or PSS shim if GSOC pub/sub not yet
landed); postage-floor enforcement; attention bonds contract on Gnosis Chain
(reuse patterns from the postage-underwriting contract work); local reputation
ratchet; RLN evaluation.

**M4 — interactive media + recommendation stages 1–2.**
WebRTC signaling profile (the **call** profile only); call/record duality;
recsys stage 1–2 (local embedding recommender R-4 + portability importer
R-5, both N=1-useful) feeding priors into the policy engine. Note: R-6
(channel directory + WebSub ingester) is independent of everything else
and can be prototyped any time from M1 onward.

- **Broadcast is explicitly out of scope for M4** (checked against Solar
  Punk Ltd's actual roadmap, 2026-07-27, not assumed): 1:N live/VOD
  streaming already has a real, active line of work (`swarm-hls-stream`,
  superseded by the in-design `Swarmcast`) that ucomm should track and
  potentially contribute control-plane thinking to, not duplicate. See
  DESIGN.md §5. ucomm's chat profile stays deliberately complementary to
  Solar Punk's existing production chat (Waku-signaled, feed-stored), not
  a replacement candidate.

**M5 — recommendation stages 3–4.**
Open-graph ingestion via the M2 bridges (ATProto, Nostr, ActivityPub,
ListenBrainz — every inbox adapter doubles as a taste-signal source); then
native privacy-preserving CF (sketch directories R-3, DP aggregation, gossip)
once there's a user base whose sketches are worth gossiping. Curation/staking
layer (R-8) alongside.

## Initial issues

Kernel (K):
- K-1 ~~Canonical encoding for envelope/genesis~~ **done** (`ucomm.encoding`;
  matches recordstore's canonical JSON format — sorted keys, compact
  separators, sha256 hex ids)
- K-2 ~~ChannelId derivation + genesis validation rules~~ **done**
  (`Genesis.validate()`/`channel_id()`: non-empty nonce, known media kinds,
  known write_policy, positive rate limit, blessed profile if set)
- K-3 ~~Causal-DAG merge with deterministic tie-break; property tests~~ **done**
  (`ucomm.log`: AuthorLog + merge_causal)
- K-4 ~~recordstore adapter for author logs~~ **done** (`ucomm.store`: one
  envelope per record, keyed by zero-padded seq for native key-order iteration)
- K-5 ~~Rendezvous interface + InMemory impl~~ **done** (`ucomm.rendezvous`);
  PSS shim still open
- K-6 MLS feasibility spike: epoch state as control events over logs
- K-7 Device subkey delegation cert format (coordinate with Swarm ID)
- K-8 ~~Profile conformance test harness (chat profile first)~~ **done**
  (`ucomm.profiles.chat`: `chat_genesis`/`validate_chat_genesis` + a minimal
  in-process `ChatChannel` exercising genesis validation, per-author logs,
  and causal-DAG merge end-to-end; no network yet)
- K-9 Relay metadata minimization survey (light clients vs PSS/GSOC full-node
  requirement)

Attention (A):
- A-1 ~~Policy engine reference impl~~ **done** (`ucomm.attention.decide`) +
  golden decision tests (Attila's four canonical examples, plus determinism
  and ceiling-monotonicity property tests)
- A-2 Bond schedule design + minimal Gnosis Chain contract sketch
- A-3 Reputation ratchet control loop: dynamics + defaults
- A-4 RLN applicability study for GSOC mailboxes
- A-5 Log-unit calibration: dogfooding protocol for defaults

Daemon/inbox (D):
- D-1 ~~Channel directory~~ **done** (`ucomm.daemon.ChannelDirectory`/
  `DirectoryEntry`: local, unsigned, single-writer; `channel_offsets`
  property feeds a `PolicyState` directly -- mute is a large negative
  offset, not a separate field, per ATTENTION.md §2)
- D-2 ~~Notification daemon core: graded dashboard~~ **done**
  (`ucomm.daemon.build_dashboard`: pure projection over directory + channel
  events + policy + clock; resolves DESIGN.md §12's open question -- never
  persisted, always recomputed, same discipline as `decide()`)
- D-3 ~~Daemon-level read-state aggregation across the whole directory~~
  **done** (`ucomm.daemon.directory_read_state`; the underlying `RECEIPT`
  interpretation moved from a chat-profile convention to
  `ucomm.log.read_state`, a kernel-level one, since `RECEIPT` is a kernel
  `EventKind` and every profile using it should mean the same thing by it --
  `ChatChannel.read_state` now calls the shared function instead of
  duplicating it)
- D-4 Push/hint delivery path (the daemon's actual "runs continuously,
  learns about new events without polling everything" half --
  `build_dashboard` takes channel events as a plain mapping today, supplied
  however the caller likes, so nothing about D-1..D-3 assumes any of the
  below). The **interface is done**: `ucomm.hints.HintSink`/`HintSource`
  (a hint is just "channel X changed, maybe look sooner," advisory,
  deduplicated) plus `InMemoryHints` for tests -- same shape as K-5's
  `Rendezvous`. **Still open, deliberately**: which real backend fills it.
  Candidates, weighed in DESIGN.md §5: Bee-native PSS; native GSOC pub/sub
  (N-2) once it lands; Waku (solves it, but doubles the stack -- though
  Solar Punk Ltd's own chat already validates the *narrow* version of this,
  Waku as a push signal only, feeds as truth, in production, not just in
  theory); a lightweight off-Swarm relay (e.g. ntfy) as an interim option.
  Whichever
  is picked, CLAUDE.md invariant 7 applies: swappable, never required for
  baseline (poll-only stays fully functional forever -- `InMemoryHints`
  with nothing ever published to it is already a legitimate use, not a
  degraded one), and labeled interim with a stated revisit condition if
  it isn't the native path.
- D-5 IMAP bridge -- **conversion layer done**: `ucomm.profiles.mail`
  (`mail_genesis`/`validate_mail_genesis`, DESIGN.md §4's mail row: open
  membership, write_policy=anyone -- unlike chat, no standing accept
  needed, matching how real email works) and `ucomm.bridges.imap`
  (`envelope_from_email`/`invitation_for_email`: pure, offline-tested with
  synthetic `email` messages, no network). Bridged envelopes are
  deliberately unsigned (`sig=""`) -- a bridge can't vouch for a foreign
  protocol's authenticity, and pretending otherwise would be worse than
  being honest that `verify_envelope` on one is always `False`.
  **Live fetch loop done** (`ImapMailbox`, via `IMAPClient` per CLAUDE.md's
  library convention): UID-tracked incremental fetch (handles the RFC 3501
  §9 quirk where a `n:*` search range always includes the mailbox's
  highest UID even when nothing new exists), per-bridged-author `seq`
  numbering, read-only (`select_folder(..., readonly=True)`). Unit-tested
  against a fake `IMAPClient` double; `tests/test_imap_bridge_live.py` is
  the opt-in real-mailbox counterpart (env-var gated, skipped by default,
  same shape as `test_bee_live.py`) -- **not yet run against a real
  server**, no test mailbox available when this was built. **Explicitly
  read-only, no SMTP**: this bridge ingests mail into the dashboard, it
  does not send or reply -- that would be a distinct, separate capability,
  not assumed to be in scope here.
- D-6 Nostr bridge

Recommendation (R) — sequencing per RECOMMENDATION.md §2: embeddings →
personal import → open-graph ingestion → native CF. R-6 has the fewest
research unknowns and is independently useful; R-4/R-5 work at N=1.
- R-1 ~~Merge prior decentralized-recsys conversation~~ **done** (v2 merged)
- R-2 Signal schema + publication tiers (private / neighborhood-ACT / public;
  implicit signals never published raw, coarse aggregates only)
- R-3 Sketch directory + neighbor-gossip protocol (MinHash/SimHash format,
  directory placement on Swarm, PSS/GSOC gossip; stamp/churn economics)
- R-4 Local embedding pipeline: multimodal embed + ANN index as
  content-addressed shared artifacts (stage 1; works at N=1)
- R-5 Portability importer (Takeout et al.) → local taste model; optional
  DP-noised donation path (selfishly-useful-first constraint)
- R-6 Community channel directory + WebSub ingester (Podcast Index model for
  YouTube: directory format, lease-refresh subscription manager, event log to
  Swarm feeds) — near-term prototype
- R-7 ATProto feed-generator prototype: CF experiments on the open firehose
  (also exercises the bridge)
- R-8 Infrastructure incentives: DVM-style paid recommendation services /
  solver ecology / RSPP assurance contracts for directories and indices
- R-9 OntoDAG/mdl-fca concept layer over usage signals (taxonomy learned from
  data; annotation-spam via MDL)
- R-10 Persona support in identity library (unlinkable per-domain key trees;
  interaction with stake/reputation — ZK candidates) [with K-7]

Naming/meta (N):
- N-1 Project name (ucomm is a placeholder)
- N-2 Message to the two Viktors: requirements ucomm puts on GSOC pub/sub
  (mailbox write rates, spam-economics hooks, light-client story)
- N-3 Share DESIGN.md + ATTENTION.md with Attila for review against his model

## Explicitly deferred

- Collaborative document editing semantics (payload-level CRDTs; Univer et al.)
- Moderation beyond sequencing (reputation-weighted, court-style escalation —
  overlaps the knowledge-base verification mechanism work; revisit at M4+)
- Marketplace/offer integration (channels as negotiation substrate for the
  universal offer schema — natural later convergence, out of scope now)
- **Closed-platform bridges: Signal, Telegram, WhatsApp, Messenger/Facebook
  feeds.** Real demand (these are daily-driver apps for a lot of people,
  including Peter), but feasibility varies sharply and none are as
  tractable as the open-protocol bridges already planned for M2 (Matrix,
  Nostr — open federated protocols; IMAP, RSS — open standards). In rough
  order of tractability:
  - **Telegram** — most tractable of the four: a public Bot API plus a
    documented MTProto client API, with established OSS bridges to learn
    from (e.g. `mautrix-telegram`). Most chats aren't E2E encrypted by
    default, which is what makes bridging technically straightforward
    (also means it's the wrong profile fit for `privacy=E2EE` channels).
  - **WhatsApp / Messenger** (both Meta) — official APIs exist but are
    business/bot-oriented, not personal-account bridging; unofficial routes
    (e.g. `whatsmeow`-based bridges) work today but are reverse-engineered,
    fragile across client updates, and ban-prone.
  - **Signal** — least tractable of the four, despite being the one
    requested first. No public bridging API at all, and Signal's
    maintainers have historically opposed third-party interoperability on
    privacy/security grounds (e.g. shutting down LibreSignal) — this isn't
    a gap that's likely to close, it's closer to a design position of
    Signal's.
  Revisit per-platform if/when picked up, not as one block — a "Signal
  bridge" and a "Telegram bridge" are different-sized problems wearing the
  same name.
