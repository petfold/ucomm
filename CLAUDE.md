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
   policy store.
5. **Advisory profiles, tested.** Apps/profiles claim named parameter bundles
   with conformance tests (anti-XMPP rule). Don't add free-form parameter
   combinations.
6. **Ephemeral = crypto-shredding.** Never present ephemerality as data
   deletion; Swarm content persists while stamps are funded.

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
- Related local projects that may be installed as dependencies later:
  recordstore (author-log persistence), swarmfs (payload blobs), mdl-fca /
  OntoDAG (recommendation layer, M4).

## Current state / next actions

- `src/ucomm/envelope.py` — M0 schema draft (dataclasses); canonical encoding
  now lives in `src/ucomm/encoding.py` (K-1, done, matches recordstore's
  format). Genesis validation + ChannelId derivation done (K-2).
- `src/ucomm/signing.py` — real signing (M1, done): `sign_envelope` /
  `verify_envelope` / `address_of`, secp256k1 + the Ethereum signed-message
  digest via `bee.swarm.keys` (the `swarm-bee` package, PyPI, pinned `>=1.1,
  <2`) — the same scheme Bee verifies SOC/feed signatures against, so a
  device key doubles as a feed signer with no translation layer. `PubKey` is
  the signer's address, not a raw public key (see module docstring for why).
- `src/ucomm/attention.py` — priority algebra + policy engine skeleton
  (issue A-1).
- `src/ucomm/rendezvous.py` — interface + InMemory impl (issue K-5).
- `src/ucomm/log.py` — `AuthorLog` + causal-DAG `merge_causal` (issue K-3,
  done).
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
