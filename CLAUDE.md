# CLAUDE.md — ucomm

Middleware for a universal communicator on Ethereum Swarm: channel kernel,
attention layer, universal inbox, discovery. Read `docs/DESIGN.md` first;
`docs/ATTENTION.md` and `docs/RECOMMENDATION.md` for the respective layers;
`docs/ROADMAP.md` for what to build next.

## Invariants — do not violate without discussion

1. **Receiver sovereignty.** Sender/channel-declared values (priority,
   importance, offsets) are advisory. `ucomm.envelope` must never import
   `ucomm.attention`; the policy engine evaluates claims, never constructs
   them. No code path may let a protocol message force a notification.
2. **Kernel minimalism.** The envelope/genesis schema is the kernel. New
   functionality goes into profiles or layers above; the kernel changes only
   with a documented spec change in DESIGN.md. If a feature "just needs one
   more envelope field," it probably belongs in a payload or a profile.
3. **Two planes.** Control-plane events (invitation, receipt, control,
   presence) stay small and structured; payloads are pointers or small inline
   blobs. Do not smuggle payload data into control events.
4. **Pure policy engine.** (envelope, policy state, clock) → intensity is a
   pure, deterministic, testable function. All mutable state lives in the
   policy store. Generalizes beyond attention: any locally-learned/derived
   view (recommendation priors, concept annotations, sketches —
   RECOMMENDATION.md §3 "truth vs. projection") must be a disposable,
   regenerable projection over authoritative signals, never itself synced
   or treated as source.
5. **Advisory profiles, tested.** Apps/profiles claim named parameter bundles
   with conformance tests (anti-XMPP rule). Don't add free-form parameter
   combinations.
6. **Ephemeral = crypto-shredding.** Never present ephemerality as data
   deletion; Swarm content persists while stamps are funded.
7. **No silent permanent dependencies.** Plan assuming full nodes and
   native GSOC/PSS pub/sub will *never* mature — treat any improvement
   there as upside, not something the plan depends on (2026-07-27, Peter,
   prompted by Levik's full-node-uptime question). Any interim/off-Swarm
   component filling a gap in the meantime (e.g. ntfy or similar as a
   hint-delivery relay while D-4 has no native path) must: (a) sit behind
   the same swappable interface the eventual native solution would use,
   never hardcoded as *the* answer; (b) never become required for baseline
   functionality — a zero-relay, poll-only path must always fully work;
   (c) be labeled interim in the doc that introduces it, with the
   condition under which it should be revisited. "Temporary" fixes that
   quietly become permanent are exactly the failure mode this exists to
   block.

## Swarm facts to respect (verified against Bee 2.8.x docs)

- GSOC = Graffiti **Single**-Owner Chunks: many writers → one shared address;
  the subscriber must be a **full node** in the mined identifier's
  neighborhood; use **mutable** stamps for GSOC. GSOC-based pub/sub is still
  being finished (Viktor Tóth, Viktor Trón) — all rendezvous code goes behind
  the `Rendezvous` interface.
- Feeds: single-owner, need **immutable** stamps.
- PSS: point-to-point; receiving node must be full to subscribe; bee-js caps
  targets at 4 hex chars.
- ACT: history-reference loss = permanent access loss; revocation is
  forward-only. Surface both in any API that touches ACT.
- Interactive media (calls, live streams) does NOT go over chunk storage:
  WebRTC data plane, Swarm control plane (signaling), optional archival back
  to the channel log.

## Repo conventions

- Python ≥ 3.11, `src/` layout, full type hints, dataclasses for schema types.
- Tests: pytest; property-based tests (hypothesis) for merge/algebra
  determinism. Run: `pip install -e ".[dev]" && pytest`.
- No premature networking: M0 is schema + algebra + in-memory implementations
  (see ROADMAP.md milestones). Bee integration starts at M1, via HTTP API
  against a local node; keep it behind thin adapters.
- Canonical encoding decisions must align with recordstore
  (github.com/petfold/recordstore) — ask before inventing encodings.
- Never hand-roll cryptography or protocol/format parsing of untrusted
  input. Use established, widely-used libraries: `coincurve`/`libsecp256k1`
  via `swarm-bee` for everything signing-related so far; for bridges,
  prefer a mature client library over the wire protocol (e.g. `IMAPClient`
  for IMAP, not raw `imaplib`) and stdlib or equally mature parsers for
  message formats (e.g. stdlib `email` for MIME) rather than a thinner or
  home-grown parser. Where a bridge needs its own crypto (e.g. Nostr's
  BIP-340 Schnorr, a different scheme from the ECDSA `ucomm.signing`
  already uses), prefer a binding backed by a serious reference
  implementation over a smaller pure-Python package, for the same reason
  `coincurve` was the right call for secp256k1.
- Related local projects that may be installed as dependencies later:
  recordstore (author-log persistence), swarmfs (payload blobs), mdl-fca /
  OntoDAG (recommendation layer, M4).

## Current state / next actions

- `src/ucomm/envelope.py` — M0 schema draft (dataclasses); canonical encoding
  now lives in `src/ucomm/encoding.py` (K-1, done, matches recordstore's
  format). Genesis validation + ChannelId derivation done (K-2).
  `Genesis.ephemeral_ttl_seconds` (Peter's feedback, 2026-07-27): a
  Signal-style configurable duration for `EPHEMERAL` persistence, validated
  against `persistence` in `Genesis.validate()`.
- `src/ucomm/signing.py` — real signing (M1, done): `sign_envelope` /
  `verify_envelope` / `address_of`, secp256k1 + the Ethereum signed-message
  digest via `bee.swarm.keys` (the `swarm-bee` package, PyPI, pinned `>=1.1,
  <2`) — the same scheme Bee verifies SOC/feed signatures against, so a
  device key doubles as a feed signer with no translation layer. `PubKey` is
  the signer's address, not a raw public key (see module docstring for why).
- `src/ucomm/attention.py` — priority algebra + policy engine (issue A-1,
  done): golden decision tests (Attila's four canonical examples) plus
  determinism/ceiling-monotonicity checks.
- `src/ucomm/rendezvous.py` — `Rendezvous` interface + `InMemoryRendezvous`
  (issue K-5, done for its intended M0/M1 scope; PSS shim still open).
- `src/ucomm/log.py` — `AuthorLog` + causal-DAG `merge_causal` (issue K-3,
  done). `read_state` (issue D-3, done) is the kernel-level convention for
  what a `RECEIPT`'s `inline` means (hex hash of the acknowledged event) --
  kernel-level because `RECEIPT` is a kernel `EventKind`, not a chat-profile
  one, so every profile using it should agree on its meaning.
- `src/ucomm/store.py` — recordstore adapter, one envelope per record (issue
  K-4, done). `recordstore[bee]` is now a real dependency (PyPI, pinned
  `>=0.11,<0.12`).
- `src/ucomm/bee.py` — `open_author_feed_log` wires `RecordStoreAuthorLog` to
  a real Swarm feed via recordstore's `BeeBytesStore`/`SwarmFeedPointer`
  (M1, done). Confirmed live against a Bee 2.8.1 node: see memory
  `bee_node_live_mainnet` for the node/stamp details — **that node is real
  Gnosis Chain mainnet with real funds, not a testnet**; never buy a postage
  batch against it without asking first. `tests/test_bee_live.py` is opt-in
  (`UCOMM_BEE_API_URL` / `UCOMM_BEE_POSTAGE_BATCH_ID` env vars), skipped by
  default so the normal suite stays offline.
- `src/ucomm/profiles/chat.py` — chat profile: `chat_genesis`,
  `validate_chat_genesis`, and an in-process `ChatChannel` (issue K-8, done).
  `ChatChannel` takes member `PrivateKey`s and really signs/verifies every
  event. `mark_read`/`read_state` give synced read-state receipts (M1, done):
  RECEIPT envelopes on the same causal chain, acknowledged event hash carried
  as a small `inline` pointer rather than in `refs`. Still in-process
  `AuthorLog`s, not wired to `ucomm.bee` yet — that swap is mechanical
  (K-4/`ucomm.bee` already prove it), not a new milestone item.
- `src/ucomm/contact.py` — out-of-band contact exchange (M1, done):
  `ContactCard` self-attests an address with a signature domain-separated
  from envelope signing (`_DOMAIN` prefix), so a card can't be replayed as,
  or forged from, a signed envelope. `to_str`/`from_str` give a compact
  pasteable/QR-able form. Deliberately not the identity-wot library (root
  keys, device delegation, petnames — standalone, tracks "Swarm ID"); no
  petname/label field, since DESIGN.md section 7 keeps those strictly local.
  **M1 is now feature-complete** per ROADMAP.md's milestone description.
- `src/ucomm/daemon.py` — M2 started: `ChannelDirectory`/`DirectoryEntry`
  (D-1, done), `build_dashboard` (D-2, done, resolving DESIGN.md §12's open
  question -- dashboard is a projection, never persisted), and
  `directory_read_state` (D-3, done: rolls up `ucomm.log.read_state` across
  every channel in the directory). No network yet -- channel events are a
  plain mapping the caller supplies.
- `src/ucomm/hints.py` — push/hint delivery abstraction (D-4's interface,
  done): `HintSink`/`HintSource` Protocols + `InMemoryHints`, same shape as
  K-5's `Rendezvous`. A hint means "channel X changed, maybe look sooner,"
  nothing more -- advisory, deduplicated, and `ucomm.daemon` never consults
  one, so a real backend can land later with zero changes to D-1..D-3. Which
  backend (Bee PSS, native GSOC pub/sub, Waku, an off-Swarm relay) is
  **deliberately not chosen yet** -- see DESIGN.md §5 and invariant 7.
- `src/ucomm/profiles/mail.py` + `src/ucomm/bridges/imap.py` — IMAP
  bridge (D-5, done, both layers): `mail_genesis`/`validate_mail_genesis`
  (DESIGN.md §4's mail row) and `envelope_from_email`/
  `invitation_for_email` (pure, offline-tested against synthetic `email`
  messages) plus `ImapMailbox` (live fetch via `IMAPClient`, now a real
  dependency, PyPI pinned `>=3.1,<4`): UID-tracked incremental fetch,
  handles the RFC 3501 §9 quirk where a `n:*` UID range always includes
  the mailbox's highest UID even with nothing new, per-bridged-author
  `seq` numbering, read-only (`select_folder(..., readonly=True)`) --
  ingests mail, never sends; SMTP is a distinct, out-of-scope capability.
  Bridged envelopes are deliberately unsigned (`sig=""`) -- a bridge can't
  vouch for a foreign protocol's authenticity, so `verify_envelope` on one
  is honestly always `False`. `ImapMailbox` is unit-tested against a fake
  `IMAPClient` double (`tests/test_imap_mailbox.py`); the opt-in real-
  mailbox counterpart (`tests/test_imap_bridge_live.py`, env-var gated,
  same shape as `test_bee_live.py`) has **not been run against a real
  server yet** -- no test mailbox was available when this was built.
  Nostr (D-6) is the rest of what's left of M2.
- `docs/RECOMMENDATION.md` is v2: the prior decentralized-recsys
  conversation is merged (R-1 done). Key commitments: sequencing embeddings →
  import → open ingestion → native CF; bridges double as taste-signal
  sources; local-first with sketches/DP/personas; ZK only for contribution
  proofs; channel-directory + WebSub ingester (R-6) is the lowest-risk first
  prototype.
- Naming: "ucomm" is a placeholder (issue N-1).

## Working style

- Prefer small, reviewable changes tied to ROADMAP issue IDs.
- When a design question arises, check DESIGN.md first; if unresolved, write
  the options into the relevant doc as an "Open question" rather than deciding
  silently in code.
- Peter reviews at the level of technical derivations; don't oversimplify —
  but don't gold-plate M0 either.
