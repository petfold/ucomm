# RECOMMENDATION — decentralized discovery and collaborative filtering

Status: v2 — conclusions from the prior conversation on decentralized
recommendation systems (2026) are merged; the `[MERGE]` markers from v1 are
resolved. Companion documents: ATTENTION.md (the negative half of relevance
estimation), DESIGN.md (kernel, bridges), ROADMAP.md (issues R-*).

## 1. Role in the communicator

Filtering and discovery are two halves of one problem: **relevance estimation
under receiver sovereignty**. The attention engine protects attention from
what's not worth it; the recommendation layer directs attention toward open
channels, broadcasts, groups, and people that are. Both emit the same output
type — a prior on value-of-attention — consumed by the same policy engine
(`prior(channel|sender) → suggested ceiling/offset`, advisory like everything
else). One scoring surface, not two systems fighting over the notification
layer.

## 2. The data problem, dissolved four ways (core conclusion)

The pessimistic framing — "no big-tech logs, no recommender" — fails because
the problem dissolves under four independent attacks, none sufficient alone:

1. **Need less data.** CF quality saturates with scale and improves mostly in
   the fat head, where recommendations are least needed; CF fails precisely in
   the long tail where a decentralized system wants to shine. Modern multimodal
   embeddings give decent cold-start recommendations with **zero usage data**
   (§3). Behavioral data is only needed for the residual — social context,
   quality, zeitgeist — a far smaller requirement than rebuilding YouTube's
   logs.
2. **Harvest data that is already open.** Large public behavioral datasets
   exist and grow daily (§4).
3. **Repatriate data users already own.** GDPR Art. 20 / portability exports
   (§5).
4. **Generate new data under privacy constraints.** Local-first CF with
   sketches, DP aggregation, and gossip (§6) — last in the sequence, once there
   are users whose sketches are worth gossiping.

Sequencing (each stage useful on its own, and at N=1 for the first two):
**embeddings → personal-history import → open-graph ingestion → native
privacy-preserving CF.**

## 3. Content-based layer: embeddings first, concepts above

- **Workhorse: multimodal embeddings** (audio, text, video frames,
  transcripts). Embed the corpus, embed the user's known-liked items, do
  nearest-neighbor search. Runs locally over millions of items; works at N=1;
  this is stage 1 and the cold-start answer.
- **Structured layer: OntoDAG / mdl-fca.** Concept annotations on channels,
  broadcasts, and identities give interpretable, compositional
  generalization that raw embedding proximity lacks, and the mdl-fca seam
  remains the research contribution: the interaction signals of §§4–6 are
  exactly the data mdl-fca learns concept DAGs *from*, so the taxonomy used
  for content-based filtering can itself be learned rather than hand-curated.
  MDL scoring doubles as annotation-spam defense: annotations that don't
  compress usage don't survive.
- Embedding indices and concept annotations are content-addressed, shareable
  artifacts on Swarm — computed once, used by many (incentive question in §9).

## 4. Open-signal ingestion: the bridges do double duty

The behavioral commons already exists; the communicator's bridge modules
(DESIGN.md §10, built for the attention firewall) are the same code needed to
ingest it. Every bridge is both an inbox adapter and a taste-signal source:

| Source | What's open | Notes |
|---|---|---|
| **ATProto / Bluesky** | entire interaction graph — likes, follows, reposts as signed public records in the firehose (Jetstream) | largest openly licensed behavioral dataset; **feed generators are a first-class protocol concept** with an official starter kit and hosted builders — the existing venue for prototyping CF on real open data (issue R-7) |
| **Nostr** | reactions and zaps as public signed events | **zaps are costly signals — sybil-resistant likes**; NIP-90 Data Vending Machines = recommendation as a purchasable service from competing providers, i.e. the solver-marketplace pattern already live |
| **ActivityPub** (PeerTube, Mastodon, Funkwhale) | boosts, favorites, comments, subscriptions federate publicly | PeerTube has the signals but **deliberately no recommender** (SepiaSearch is anti-algorithmic by philosophy); corpus is small (~1.5M videos), so embeddings matter more than CF there — a recommender over it is new but unobstructed code |
| **ListenBrainz** | open listen database with full dumps + an open-source CF pipeline (troi) | music is largely solved in the open; glue, don't build |
| **Podcast Index / RSS / OPML** | open directory + API; the medium never lost RSS | solved |

The genuinely novel artifact — built by nobody — is the **cross-channel
unification layer**: joining PeerTube, ListenBrainz, ATProto, RSS (and ucomm-
native) behavior into one taste model. Crucially it is a *client-side*
artifact: it can start as a local-first aggregator with no network protocol at
all.

## 5. Data repatriation via portability rights

Users legally own their histories (GDPR Art. 20 and equivalents; Takeout et
al.). A client-side importer ingests the user's own export and (a) immediately
seeds a personal recommender with years of data — works at N=1 — and (b)
*optionally* contributes a DP-noised sketch to the commons. This drains the
value of already-collected data through the individuals who own it, instead of
recreating the surveillance. **Design constraint: the tool must be selfishly
useful first; donation is a side effect, never the ask.**

## 6. Native layer: local-first, model-to-data

The privacy problem largely dissolves by inverting the topology: the full
history never leaves the device; what gets published are compact,
privacy-budgeted artifacts.

- **Sketches for neighbor discovery.** MinHash/SimHash signatures of the item
  set let peers estimate Jaccard similarity without learning items. Neighbor
  discovery = "find users with close sketches" — exactly what CF needs.
  Published to **sketch directories** (content-addressed on Swarm); gossip
  between similarity neighbors over PSS/GSOC.
- **DP-noised aggregates via secure aggregation** (federated-learning style)
  for global popularity and co-occurrence statistics with no individual
  reconstructable. Existing libraries (Flower, OpenDP) cover the primitives;
  the deployed decentralized product does not exist — this is new code.
- **Pseudonymous per-domain personas**: jazz taste and politics reading need
  not be linkable. Cheap, and solves ~80% of practical privacy before any ZK
  machinery. Ripples into the identity library: personas are unlinkable
  device-key trees under one root the user controls (issue K-7b).
- **ZK held in reserve for contribution proofs**, not recommendations
  themselves — e.g. proving "this rating comes from someone who actually
  retrieved the content" (proof-of-retrieval) against sybil spam.
- **Gossip CF** has a real literature; convergence is slower than centralized
  SGD, but taste drifts slowly, so that's tolerable.
- **WoT gating retained from v1** as the pool-admission rule: trust decides
  *whose* sketches/signals you learn from (sybil defense); similarity decides
  *how much* (weighting). Trust and taste stay distinct axes.

Watch-time — the strongest implicit signal — requires client instrumentation,
which is a reason the trojan horse must be a client people want to use. For
ucomm this converges neatly: the communicator's own receipts and engagement
events (kernel-native envelopes) *are* the instrumentation, generated on the
open side under the user's control.

## 7. Curation: the social layer as a substitute for scale

Underrated and data-cheap: humans do the compression. Users follow curators;
curators stake reputation (or tokens) on recommendations; trust propagates
transitively with decay. The algorithm's job shrinks to **routing** — matching
users to curators, and personalized re-ranking of what the trust neighborhood
surfaces. Small interest-dense communities routinely beat global recommenders
within their domain; the system should embrace being a **federation of niche
recommenders**, not one global one. Staked/bonded endorsements are the same
mechanism family as attention bonds (ATTENTION.md §4), same settlement layer.

## 8. Observing closed platforms

For content that mostly appears on big tech, treat the platform as a **dumb
content host observed through open feeds**, and generate interaction data
client-side (§6).

- **Per-channel monitoring is solved**: YouTube exposes per-channel Atom feeds,
  and WebSub (PubSubHubbub) push notifications on those topics — free,
  account-less, the NewPipe/FreeTube pattern. Caveat: subscriptions lease and
  must be refreshed (housekeeping).
- **No global firehose exists**; the real gap is *channel discovery*. In
  descending cleanliness: Data API search (tiny quota, restrictive ToS — seed
  only), snowball crawling via **out-of-band mentions** (channels announced on
  Bluesky/Mastodon/Reddit/show notes — the open social layer as a discovery
  sensor for closed platforms), Invidious/Piped (ToS-grey, actively blocked —
  sand, not foundation).
- **Community-maintained channel directory** — the Podcast Index model applied
  to YouTube: a curated, openly licensed list of channel IDs with topic tags,
  plus WebSub subscriptions across it, yields a legal push-based feed of new
  content over ~100k channels at trivial cost. Curation is decentralizable and
  Swarm-storable, and sybil-resistant in a way behavioral scraping is not,
  because **inclusion is an explicit curatorial act** (and can be staked, §7).
- Mitigating trends: podcast-first creators now push RSS upstream of YouTube
  (the canonical open feed exists, YouTube is a mirror), and creators
  increasingly announce on open networks even when hosting stays closed.
- The directory + WebSub ingester (directory format, subscription manager,
  event log to Swarm feeds) is the piece with the **fewest research
  unknowns** — prototype-in-days territory (issue R-6).

## 9. Attack surface and incentives

Sybil defenses, in order of load-bearing: (1) costly signals — zaps, stake,
proof-of-retrieval — free public likes are spam-farm bait; (2) trust-graph
gating of the learning pool; (3) postage cost on published signals; (4) local
per-user models — there is no global ranking to capture; an attacker must
compromise *your* neighborhood, not "the algorithm"; (5) curated directories
over scraped behavior (§8).

The deeper open problem is not data but **incentives for the boring
infrastructure**: index maintenance, embedding computation, sketch
directories, directory curation. Framings on the table: recommendation-as-
matching as a paid service from competing providers (Nostr's DVM pattern is
this, live today; also the solver-ecology framing from the marketplace work),
and RSPP-style assurance contracts for recurring public-good infrastructure
funding. Issue R-8.

## 10. Interfaces

- → attention engine: priors as suggested ceilings/offsets; advisory only;
  cold-start with no signal reduces to WoT distance — recovering ATTENTION.md
  §5's `ceiling = base − k·d` as the zero-information special case.
- → inbox/dashboard: discovery pane = dashboard sorted by recommendation prior
  instead of effective priority.
- ← identity/WoT: neighborhood construction, personas (§6), curator trust.
- ← bridges: every inbox adapter is a signal source (§4).
- ← kernel: all native signals are ordinary envelopes; no new event machinery.

## 11. Open questions

- Publication tiers and granularity of shared aggregates: how coarse can
  engagement sketches be while preserving CF value (information-theoretic
  framing available).
- Negative signals (mutes, ceiling ratchets) are strong but socially fraught
  to share — aggregate-only, persona-only, or never?
- Sketch directory placement and refresh economics on Swarm (stamp sizing vs.
  churn).
- Persona unlinkability vs. bond/stake reputation: staking is identity-linked
  by nature; can a persona carry stake without linking back? (ZK candidates.)
