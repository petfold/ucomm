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
  format). Genesis validation + ChannelId derivation done (K-2). Real
  signatures are still a placeholder string — M0 only calls for signature
  stubs (ROADMAP.md milestone M0); real signing is expected at M1 once
  device keys exist.
- `src/ucomm/attention.py` — priority algebra + policy engine skeleton
  (issue A-1).
- `src/ucomm/rendezvous.py` — interface + InMemory impl (issue K-5).
- `src/ucomm/log.py` — `AuthorLog` + causal-DAG `merge_causal` (issue K-3,
  done).
- `src/ucomm/store.py` — recordstore adapter, one envelope per record (issue
  K-4, done). `recordstore` is now a real dependency (PyPI, pinned `>=0.11,
  <0.12`).
- `src/ucomm/profiles/chat.py` — chat profile: `chat_genesis`,
  `validate_chat_genesis`, and an in-process `ChatChannel` (issue K-8, done).
  No network yet — `ChatChannel` holds plain `AuthorLog`s; swapping in
  `RecordStoreAuthorLog` or a real feed is the M1 step, not a rewrite.
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
