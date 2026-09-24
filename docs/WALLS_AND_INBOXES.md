# WALLS AND INBOXES — posting to an audience, reading what arrives (ucomm's side)

Status: draft for discussion (2026-09-24). Nothing here is built. This is
ucomm's fold of a design shared with OntoDAG and categor.io. **The canonical
statement, with the definitions, is OntoDAG's
`docs/plans/WALLS_AND_INBOXES.md`**; this note says what it means for the
channel kernel, the attention engine and the inbox, and what ucomm would
build. Companions: DESIGN.md §4 (profiles), §8 (encryption), §10 (inbox);
RECOMMENDATION.md §3 (the OntoDAG concept layer).

## 1. The idea in ucomm's words

- **A wall** is an author's outbox: their posts in the order they posted
  them. Each post has an **audience** the author chooses — one person (a
  chat), a small group, a large group, or everyone.
- **An inbox** is the reader's side: the walls they follow, merged. It is
  the universal inbox (DESIGN.md §10), seen as a timeline.
- **Receivers do not need to know other receivers.** An author who wants
  them to know says so in the post; nothing in the protocol lists them.

ActivityPub has the same two collections (*outbox* and *inbox*); Mastodon
calls the inbox side the "home timeline".

**Not "feed".** A Swarm feed is one owner's sequence of updates under a
topic, which is how ucomm already stores author logs (DESIGN.md §3.1). A
wall is *published as* a Swarm feed; the reader's side is never called a
feed here.

## 2. A wall is a social-profile channel of one author

The `social` profile (DESIGN.md §4: 1:N plus a reply graph, follow =
standing accept, low ceiling) is the wall. Its genesis:

| Parameter | Value for a wall |
|---|---|
| profile | `social` |
| ordering | per-author independent |
| write policy | single broadcaster (the author) |
| persistence | permanent |
| privacy | ACT-gated, per post (below) |
| membership | open to follow; *reading* each post is gated by its audience |

- **The audience is per post, not per channel.** Each post's payload is
  encrypted under its own key (the per-document keys of OntoDAG's
  act-categories design, §2.4 there). That key is reachable from exactly the
  audience's category keys: one person, a group, or `everyone`. One log per
  author, and each post chooses its own audience. The alternative, a
  channel per audience, is simpler but multiplies channels, and which
  channels exist would leak the audiences (open question W-Q1).
- **Replies** are posts on the replier's own wall whose `refs` cross
  channels, which DESIGN.md §4 already allows ("subject to the target's
  privacy").
- **A chat can be two walls addressed to each other**, read as one feed.
  The existing `chat` profile stays as it is (causal-DAG, shared channel);
  walls are for 1:N and for readers who follow rather than join.

## 3. The inbox is the universal inbox, as a timeline

- **Following** = a channel-directory entry for the author's wall at a low
  ceiling, as DESIGN.md §4 defines a follow. The directory stays the one
  authoritative, user-curated piece of daemon state (§12 there).
- **The inbox timeline** is the dashboard sorted by publish time, next to the
  existing sort by effective priority, the way RECOMMENDATION.md §10 already
  describes a discovery pane as "the dashboard sorted by recommendation
  prior". It is a projection, recomputed and never stored (invariant 4).
- **What interrupts** is still decided by the attention engine, post by
  post. Most posts from a follow sit below threshold and are just *there*
  in the inbox; a post that clears the reader's threshold rings.

## 4. Time

**Envelopes carry no clock time**: order is per-author `seq` plus causal
`refs`, and that stays so (invariant 2: kernel minimalism). A post's
publish time is its `posted` value in OntoDAG terms (a role of `time`),
carried in the payload's metadata or in the post's projection into
OntoDAG. It is the author's claim, advisory like every sender claim
(invariant 1). Within one author, `seq` fixes the order regardless of
what time is claimed; an inbox may sort by the claim and break ties, or
detect back-dating, by `seq`.

## 5. What OntoDAG gives ucomm

- **Audiences with structure.** Who a post is for is reach in the author's
  store: principals and groups filed under them, nested (sales has all
  that employees have), with receivers never seeing each other. That is
  richer than a flat member list, and it is the same definition ACT's
  category keys are derived from.
- **Concepts.** Posts classified with the public vocabulary make the inbox
  queryable (`dog`, posted this month, from these authors). This is
  RECOMMENDATION.md §3's structured layer, and issue R-9's seam.
- **The projector.** The envelope → facts projector OntoDAG's
  `PROJECTIONS.md` assigns to ucomm extends to posts. Its facets go under
  `sys:` (`sys:from:<address>`, `sys:channel:<id>`), so a projected
  "from Alice" never reads as "shared with Alice". This is exactly how
  OntoDAG's SHARING.md open question Q1 wants principals and facets kept
  apart.

## 6. What ucomm gives OntoDAG hosts (categor.io first)

- **Delivery without a server**: walls on author logs over Swarm feeds,
  poll-only by default, hints when a relay is available (invariant 7).
- **Graded consent**: categor.io's "requests" (a first share from someone
  you have not accepted) are ucomm invitations, and its per-address
  show/hide setting is a coarse version of ceilings and thresholds. The
  pure policy engine (A-1) can replace it.
- **Identity**: key-based identities, device subkeys and unlinkable
  personas (K-7, R-10) for the pseudonyms categor.io's roadmap lists.

## 7. Invariants check

1. **Receiver sovereignty.** The author chooses an audience; the reader
   chooses the inbox and what interrupts. The `posted` time is advisory.
2. **Kernel minimalism.** No new envelope field: time and audience live in
   payloads and keys.
3. **Two planes.** Posts are data plane; "a new post on a wall you follow"
   is a small control-plane event, if one is sent at all.
4. **Pure projections.** The inbox timeline is a projection of the directory
   and the walls.
5. **Profiles, tested.** The wall is the `social` profile, which needs its
   conformance suite before anything claims it (issue W-1).
6. **Ephemeral = crypto-shredding.** Unchanged, and so is forward-only
   revocation: a reader removed from an audience keeps what they already
   had (DESIGN.md §8).
7. **No silent dependencies.** Walls are read by polling their Swarm
   feeds alone; hints are optional.

## 8. Open questions (ucomm's side)

- **W-Q1** per-post keys or a channel per audience (§2);
- **W-Q2** does "new post" need a control-plane event, or is the log
  update itself the signal (a follow is low-ceiling by definition)?
- **W-Q3** inbox ordering: claimed `posted` time, `seq`, or both (§4);
- **W-Q4** replies across channels whose audiences differ: what does a
  reader who cannot see the original see?

The shared questions (where `posted` is declared, ACT time buckets,
cross-store names for replies, post identity) are in OntoDAG's note, §8.
