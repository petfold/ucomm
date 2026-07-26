# ucomm — universal communicator middleware for Ethereum Swarm

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
CLAUDE.md               Instructions and invariants for Claude Code sessions
src/ucomm/              Python prototyping track (schema, policy engine, interfaces)
tests/                  pytest suite
```

## Status

Design phase. The Python package contains the envelope schema, the priority
algebra, and the pluggable `Rendezvous` interface — enough to prototype
known-contact channels over Swarm feeds today. Open GSOC-based rendezvous
(unsolicited contact, group discovery) is behind an interface, pending the
GSOC/pub-sub work by Viktor Tóth and Viktor Trón.

## Related projects

- **recordstore** (github.com/petfold/recordstore) — candidate persistence substrate
  for author logs (versioned key → record over Swarm; POT track).
- **swarmfs** (github.com/petfold/swarmfs) — fsspec backend, useful for payload blobs.
- **OntoDAG / mdl-fca** — semantic concept DAG; content-based half of the
  recommendation layer.
- Attila Lendvai, *Computer aided human communication*
  (codeberg.org/attila.lendvai/publications) — source of the attention taxonomy.
