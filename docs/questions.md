# What this project answers

**The question a head of product would ask:** we're losing subscribers. Which
ones, why, and what should we change?

That breaks down into six questions the data can actually answer. Each one
feeds a decision; none of them is there just to produce a chart.

## 1. How big is the problem, and is it getting worse?

Subscribers at the start of each month, plus new, won back, churned, at the
end. Churn rate by month.

*Feeds:* whether churn is the problem to work on at all, and the baseline any
target is measured against.

## 2. Where in the lifecycle do we lose people?

Trial → first payment → first renewal → long-term subscriber. Where is the
biggest drop, and how many subscribers does each step cost us?

*Feeds:* whether to invest in onboarding, renewal or win-back first.

## 3. Which subscribers churn the most?

Renewal type (auto-renew vs manual), payment method, plan length, sign-up
channel, trial vs direct start. Many of these overlap, so the work is to find
which ones matter on their own and which are the same people seen twice.

*Feeds:* which segment to target first, sized by subscribers and revenue at stake.

## 4. Are newer customers worse than older ones?

Retention curves by sign-up month and channel. The channel mix changed a lot
in 2016, so a drop in retention could be a channel effect, not a product one.

*Feeds:* acquisition channel quality.

## 5. Does listening behaviour warn us before someone leaves?

Listening in the weeks before a subscription ends vs before a renewal. And
activation: what new subscribers do in their first two weeks, and whether it
predicts who stays.

*Feeds:* an early-warning trigger for retention campaigns, and a working
definition of an "activated" subscriber.

## 6. Who comes back, and is winning them back worth it?

Win-back rate, time to return, and how long and how profitably returning
subscribers stay the second time.

*Feeds:* whether a win-back campaign is worth running, and when to send it.

## How it ends

The case study closes with one or two recommendations. Each comes with a test
design: the metric, the smallest effect worth detecting, the sample size and
how long to run it. No claimed impact: public data has no revenue to lift.

## What the data can't answer

- **Feature-level product changes.** There are no product events (screens,
  search, playlists), only billing and daily listening totals.
- **Acquisition cost and payback.** There is no marketing spend.
- **Price sensitivity.** Discounts are rare (1.4% of payments), so there's no
  price variation to learn from.
- **Demographics.** Age and gender are missing for two thirds of users.

## Definitions

Subscription, churn, win-back and trial are defined in
[data_notes.md](data_notes.md), along with the checks behind them.
