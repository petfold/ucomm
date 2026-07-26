# ATTENTION — priority model, policy engine, and incentive mechanisms

Source model: Attila Lendvai, *Computer aided human communication*
(codeberg.org/attila.lendvai/publications). This document formalizes that model
and adds the mechanisms needed to make sender-declared priority survive
adversaries — Attila's own opening observation (LLMs marginalize the cost of
spamming humans) implies any free-to-claim priority field gets pinned at maximum
by bots. Claims must be costly signals.

## 1. Definitions

An **attention request** (invitation) is a control-plane envelope carrying an
`AttentionClaim`:

- `importance` ∈ ℤ (claimed, log-scale units)
- `urgency` ∈ ℤ (claimed, log-scale units)
- `relevance`: time window [t₀, t₁] after which the request self-expires
- `interactivity` ∈ [0, 100]: requested continuity of attention
  (voice call ≈ 90–100, chat 0–100, letter 0)
- `expected_duration`: if interactive
- `collateral`: optional bond reference or stamp proof (§4)

## 2. Priority algebra (log-scale)

Refinement over the multiplicative original: all quantities live in log-scale
("dB-like") units so that every adjustment in the model is **additive and
composable**:

```
claimed_priority   = importance + urgency                    (sender, advisory)
effective_priority = min(claimed_priority, ceiling(sender))  (receiver-side cap)
                     + channel_offset                        (e.g. muted group: −30)
                     + endpoint_offset                       (e.g. in a call: raises bar)
                     + credibility(sender, collateral)       (§4; can be negative)
residual           = effective_priority − threshold(now)     (DND is just a high threshold)
```

Current `decide()` only implements the non-negative bond-credit case above
(`bond_credit` if collateral is valid, else 0); a reputation-based penalty
(negative credibility for a known-bad actor) is A-3's reputation ratchet,
not yet built.

Attila's examples map directly: smoke from the house = high importance + high
urgency; "beer in 2 hours" = high urgency + low importance + 2 h relevance
window; doctor checkup = high importance + low urgency; tennis schedule = low +
low. Ceilings, offsets, thresholds are his terms, unchanged — only the units are
made additive.

## 3. Graded notification (policy engine output)

The engine outputs an **intensity**, not a boolean, from the residual:

| residual | behavior |
|---|---|
| ≫ 0 | full alert (breaks through DND if residual clears the DND threshold) |
| slightly > 0 | soft alert: ring once, or vibrate only |
| slightly < 0 | badge/dashboard only, no interruption |
| ≪ 0 | silently filed; visible in dashboard history |

This realizes the graded-response idea (a near-threshold call rings once; a
known contact's high-priority message in a silenced group can still surface).

Determinism requirement: the mapping (envelope, local policy state, clock) →
intensity is a pure function. All state lives in the policy store; this is what
makes the decision auditable ("why did this ring?") and testable.

## 4. Making claims costly: three stacked mechanisms

1. **Postage floor.** Every write to Swarm costs postage. Unlike email and
   Nostr, sending is never free. This alone kills zero-cost bulk spam and is a
   structural advantage of building on Swarm.

2. **Attention bonds.** To claim priority above the default ceiling toward a
   recipient outside your WoT, attach a slashable deposit scaled to the excess
   claim. The recipient's client may keep it (claim judged dishonest) or return
   it (honest). This is the Loder / Van Alstyne / Walsh attention-bond design,
   finally with a practical settlement layer (Gnosis Chain, where postage
   already lives). Policy: `required_bond = f(claimed_priority − ceiling)`,
   receiver-configurable. Honest high-priority strangers pay a refundable
   deposit; spammers face expected loss per message.

3. **Local reputation ratchet.** A sender who cries wolf gets their per-contact
   ceiling automatically lowered (and slowly recovered). Purely local state — no
   global reputation system, no oracle, nothing to game at the network level.
   Attila's "−10 ceiling for a week" becomes an automatic control loop with
   manual override.

For **open GSOC mailboxes** (unsolicited contact — the highest-pressure point),
add **RLN** (rate-limiting nullifiers, as deployed by Waku): zero-knowledge
per-epoch rate limits without identifying senders. Mailbox admission = valid
stamp + RLN proof + (bond if claiming above stranger-default ceiling).

## 5. WoT-derived defaults

Default ceiling for a sender at WoT distance d: `ceiling = base − k·d`, with
true unknowns (no WoT path) needing collateral to reach notification threshold
at all. The recommendation layer (RECOMMENDATION.md) refines this from
topological distance toward learned trust/taste similarity — a stranger warmly
attested by two taste-neighbors gets a milder default than raw distance implies.

## 6. Dashboard model

Two views, per the source model:
- **Active**: currently relevant requests ordered by effective priority,
  including sub-threshold ones (missed/filed calls land here, not in a separate
  app's call log).
- **Obsolete timeline**: expired or answered requests, marked
  accepted/answered or not, filterable by initiator.

Relevance expiry is enforced by the daemon: expired requests transition to the
timeline without ever interrupting.

## 7. Receiver-side configuration surface

- Global threshold slider (DND is the top of the scale, with per-sender
  exception ceilings above it).
- Per-contact ceilings with temporary adjustments (auto-ratchet §4.3 + manual).
- Per-channel offsets (mute = large negative offset, not a separate mechanism).
- Bond schedule `f` and stranger defaults.
- All of it is local policy state — never published, never negotiated.

## 8. Open questions

- Bond adjudication UX: keeping a bond is a social act; defaults should make
  "return" the path of least resistance and "keep" deliberate.
- Collusion in bond returns (sender = recipient sybil) is harmless (money moves
  between own accounts) but check second-order effects with RLN membership.
- Calibration: what do +10 log-units mean to a human? Needs empirical anchoring
  with a small user study or dogfooding defaults.
- Priority of *reply* traffic in an accepted interactive channel: standing
  acceptance should imply an elevated floor for the session's duration
  (endpoint offset), decaying after.
