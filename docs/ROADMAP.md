# ROADMAP — modules, milestones, initial issues

## Module decomposition (standalone where independently useful)

Per Attila's implementation note, components useful outside the communicator are
standalone libraries with their own repos once stable:

| Module | Scope | Depends on | Standalone? |
|---|---|---|---|
| `ucomm.envelope` | envelope + genesis schema, canonical encoding | — | eventually (schema lib) |
| `ucomm.signing` | secp256k1 signing/verification (`sign_envelope`, `verify_envelope`) | envelope, `swarm-bee` | **yes** — a generic Bee-compatible envelope signer |
| `ucomm.log` | per-author append-only channel logs | recordstore | no (thin adapter) |
| `ucomm.rendezvous` | `Rendezvous` interface; InMemory / PSS-shim / GSOC impls | Bee API | no |
| `ucomm.attention` | priority algebra + policy engine (pure functions + policy store) | envelope | **yes** — useful for any notification system |
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
- Still open: author logs actually on Swarm feeds (currently in-process
  `AuthorLog`/`RecordStoreAuthorLog`, no network); out-of-band contact
  exchange; read-state receipts.

**M2 — daemon + universal inbox + first bridges.**
Notification daemon with graded alerts and dashboard (active/obsolete);
channel directory; PSS hint path via a full node; IMAP and Nostr bridges —
the **attention firewall** as standalone value.

**M3 — rendezvous + spam economics.**
GSOC mailboxes for unsolicited contact (or PSS shim if GSOC pub/sub not yet
landed); postage-floor enforcement; attention bonds contract on Gnosis Chain
(reuse patterns from the postage-underwriting contract work); local reputation
ratchet; RLN evaluation.

**M4 — interactive media + recommendation stages 1–2.**
WebRTC signaling profile; call/record duality; recsys stage 1–2 (local
embedding recommender R-4 + portability importer R-5, both N=1-useful) feeding
priors into the policy engine. Note: R-6 (channel directory + WebSub ingester)
is independent of everything else and can be prototyped any time from M1
onward.

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
- K-5 Rendezvous interface + InMemory impl (in skeleton) → PSS shim
- K-6 MLS feasibility spike: epoch state as control events over logs
- K-7 Device subkey delegation cert format (coordinate with Swarm ID)
- K-8 ~~Profile conformance test harness (chat profile first)~~ **done**
  (`ucomm.profiles.chat`: `chat_genesis`/`validate_chat_genesis` + a minimal
  in-process `ChatChannel` exercising genesis validation, per-author logs,
  and causal-DAG merge end-to-end; no network yet)
- K-9 Relay metadata minimization survey (light clients vs PSS/GSOC full-node
  requirement)

Attention (A):
- A-1 Policy engine reference impl (in skeleton) + golden decision tests
- A-2 Bond schedule design + minimal Gnosis Chain contract sketch
- A-3 Reputation ratchet control loop: dynamics + defaults
- A-4 RLN applicability study for GSOC mailboxes
- A-5 Log-unit calibration: dogfooding protocol for defaults

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
