# ucomm — universal communicator middleware for Ethereum Swarm

[![license](https://img.shields.io/badge/license-BSD--3--Clause-blue)](LICENSE)
[![status](https://img.shields.io/badge/status-M2%20in%20progress-yellow)](docs/ROADMAP.md)

*Working title. Naming is an open question (see ROADMAP.md, issue N-1).*

Every communication app — chat, email, calls, streams, forums, social feeds — moves
information of some kind from one or more people to one or more people. The apps
differ in a handful of parameters (topology, interactivity, persistence, privacy,
invitation granularity), not in principle. Yet on Swarm, as elsewhere, each project
rebuilds the same primitives from scratch and ships its own silo, its own inbox,
and its own notification settings.

**ucomm** is middleware that factors out the common core:

- a **channel kernel**: a channel is a set of per-author append-only logs, a merge
  rule, and a parameter vector fixed at genesis; every event is one signed envelope.
- an **attention layer**: a first-class control plane for requesting human attention,
  based on Attila Lendvai's priority taxonomy (importance × urgency, ceilings,
  offsets, thresholds), made incentive-compatible with postage costs, attention
  bonds, and local reputation.
- a **universal inbox**: one local notification daemon per device arbitrates all
  attention requests across all channels and apps; apps become views and policy
  defaults, not silos.
- a **discovery/recommendation layer**: WoT-weighted collaborative filtering plus
  concept-based (OntoDAG) content filtering, feeding priors into the attention
  engine.

Guiding principle: **receiver sovereignty**. Everything a sender or channel declares
(priority, offsets, importance) is advisory and signed; the receiver's local policy
engine is the only authority over the receiver's attention.

## Repository layout

```
docs/DESIGN.md          Architecture: two planes, channel kernel, profiles, transports
docs/ATTENTION.md       Attention economy: priority algebra, policy engine, mechanisms
docs/RECOMMENDATION.md  Discovery & collaborative filtering (needs merge from prior notes)
docs/ROADMAP.md         Module decomposition, milestones, initial issues
docs/USER_GUIDE.md      Tutorial: motivation, project overview, install, worked examples
CLAUDE.md               Instructions and invariants for Claude Code sessions
src/ucomm/              Python package (schema, policy engine, signing, chat profile)
tests/                  pytest suite
```

## Status

**M0 (schema + algebra) and M1 (known-contact channels over Swarm) are done**
— see `docs/ROADMAP.md` for the full milestone/issue breakdown. Concretely:
the envelope/genesis schema with canonical encoding and validation; the
priority algebra and policy engine with golden decision tests; per-author
logs with deterministic causal-DAG merge, backed by either an in-memory
implementation or a real recordstore/Bee adapter; real secp256k1 envelope
signing (via `swarm-bee`) and out-of-band contact exchange; and a two-party/
group chat profile exercising all of the above end-to-end, confirmed against
a live Bee node. New here? Start with `docs/USER_GUIDE.md`.

**M2 (notification daemon + universal inbox) is in progress**: a private
channel directory, a graded active/obsolete dashboard (a projection,
recomputed on demand — never persisted), read-state aggregation across
every channel, a push/hint-delivery interface, and the IMAP bridge's
conversion layer (email → the same envelopes and dashboard, no live
mailbox yet) are done. Left: an actual hint backend, IMAP's live fetch
loop, and the Nostr bridge — see `docs/USER_GUIDE.md` sections 11–13 for
the directory/dashboard/hints/bridge demos. GSOC-based rendezvous
(unsolicited contact, group discovery) stays behind the `Rendezvous`
interface, pending the GSOC/pub-sub work by Viktor Tóth and Viktor Trón.
Broadcast-style 1:N live streaming is explicitly out of scope here —
Solar Punk Ltd's own `swarm-hls-stream`/`Swarmcast` line already owns that
(DESIGN.md §5).

**On decentralization, read this before evaluating further:** everything
above runs on Swarm feeds and needs no full node — a light client is
enough. Real-time push notification and unsolicited-contact discovery (PSS
and GSOC) are a different story: both require a full node, yours or a
relay's, and that relay sees traffic metadata, which is a real
centralization point still unresolved (not just a caveat) — see
`docs/DESIGN.md` §5 and §11. Nothing here should be evaluated as "fully
decentralized" without that qualification.

## Related projects

- **recordstore** (github.com/petfold/recordstore) — candidate persistence substrate
  for author logs (versioned key → record over Swarm; POT track).
- **swarmfs** (github.com/petfold/swarmfs) — fsspec backend, useful for payload blobs.
- **OntoDAG / mdl-fca** — semantic concept DAG; content-based half of the
  recommendation layer.
- Attila Lendvai, *Computer aided human communication*
  (codeberg.org/attila.lendvai/publications) — source of the attention taxonomy.
