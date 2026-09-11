# Findings

The analysis behind the case study, question by question. Charts and the
written case study come next; this is the working record of what the data
says.

Churn here means the membership lapsed for more than 30 days, with billing
gaps excluded (see [data_notes.md](data_notes.md)). Money is in New Taiwan
dollars (NT$).

## The short version

- **Paying subscribers grew 30% in 14 months**, from 904k to 1.18M. But about
  3.3% leave every month, 33–43k people. That's about as many as the new
  subscribers who arrive.
- **Churn is mostly about how people pay.** Manual renewals are 13% of renewal
  decisions but 57% of churn. With everything else held fixed, a manual
  renewal is about four times as likely to end in churn as an auto-renewal.
  And it's not only who these people are: manual payers who switched to
  auto-renew churned at about a third of the rate of those who stayed manual.
- **The first renewal is where new subscribers are lost.** It's 7% of renewal
  decisions and 34% of churn. Manual payers at their first renewal are 3.5% of
  decisions and 28% of all churn.
- **Channels, long plans and free trials look bad in the raw numbers**, but
  once payment type and tenure are accounted for, the differences almost
  disappear. It's the same manual payers seen from another angle.
- **Listening is a strong warning sign for manual payers only.** A manual payer
  who didn't listen in the four weeks before renewal churns 79% of the time.
- **About a third of churned subscribers come back within six months**, mostly
  people whose auto-renew payment simply stopped. People who cancelled rarely
  return, and returning subscribers are worth less than new ones.

**Recommendation:** get manual payers onto auto-renew, starting at checkout
for new subscribers in channels 3, 4 and 9. Test it before rolling it out.

## 1. How big is the problem?

`marts.monthly_subscribers`, paying subscribers only. 2015 is a warm-up year
(anyone subscribed before 2015 looks new), so the story starts in 2016.

| | Jan 2016 | Jun 2016 | Dec 2016 | Feb 2017 |
|---|---|---|---|---|
| Subscribers at start of month | 903,962 | 1,008,559 | 1,131,044 | 1,164,827 |
| New | 76,538 | 39,018 | 43,363 | 37,862 |
| Returning | 15,333 | 13,006 | 17,064 | 12,129 |
| Churned | 32,861 | 32,839 | 42,670 | 38,363 |
| Churn rate | 3.6% | 3.3% | 3.8% | 3.3% |

- Monthly churn sits at 3.1–3.8% in a normal month. It peaks in February and
  March 2016 (5.9% and 5.2%) and is higher every December.
- New subscribers slowed down: about 49k a month in the first half of 2016,
  40k in the second half, 37k in early 2017. Churn didn't slow, so growth now
  leans on returning subscribers.
- The February 2016 peak is partly a batch: 17,480 subscriptions on one
  payment method ended on the same day, 25 Feb 2016. Those people had mostly
  stopped listening already; only 15% listened in 6 or more of the previous
  8 weeks. The rest is the big January 2016 intake leaving at its first renewal.
- Revenue per subscriber is about NT$130 a month (the list price is NT$149).

## 2. Where in the lifecycle do we lose people?

New users only: registered from 2015 on, so their whole history is visible.

- **Free trials barely convert.** 224k new users started with a 7-day free
  trial and 4.4% of them ever paid. Channel 4, where most trials come from,
  converts 2.3%; channel 3 6.3%; channel 9 10.7%.
- **Trial converts churn faster.** About 45% of them are still subscribed a
  year after their first payment, against 65% of people who paid from day one.
- **The first renewal is the big drop.** 11.4% of new paying subscribers leave
  at their first renewal. After that it's 4.8%, 4.0%, then 2–3% a month.
- About 65% of new subscribers are still paying a year after their first
  payment, 57% after 18 months.
- **Longer first plans delay churn but don't prevent it.** 18 months after the
  first payment, 50% of people who started on a 3–12 month plan are still
  subscribed, against 58% of people who started monthly.

## 3. Which subscribers churn the most?

The unit here is a renewal decision: every time a paid period ends, the
subscriber either pays again or leaves. There were 10.15M decisions in 2016,
and 4.56% ended in churn.

Many factors overlap: manual payers are more often new, on long plans or from
channels 3, 4 and 9. A logistic regression on a random sample of 600k
decisions separates them. "Adjusted" is the churn rate with every other factor
held at its real mix.

| Factor | Level | Raw churn | Adjusted |
|---|---|---|---|
| Payment | Auto-renew | 2.3% | 2.6% |
| | Manual | 19.2% | **11.4%** |
| Tenure (payment number in the subscription) | 1st | 21.0% | **10.8%** |
| | 2nd | 9.4% | 5.9% |
| | 3rd | 6.3% | 4.7% |
| | 13th or later | 2.3% | 3.2% |
| Plan | Monthly | 4.0% | 4.5% |
| | 3–6 months | 25.6% | 5.2% |
| | 12+ months | 33.3% | 5.3% |
| Started with a free trial | No / Yes | 4.5% / 14.4% | 4.5% / 4.1% |
| Channel | 7 | 1.6% | 4.6% |
| | 9 | 6.6% | 4.1% |
| | 3 | 9.7% | 4.1% |
| | 4 | 14.6% | 4.2% |

- **Payment type and tenure carry the signal.** Channel, plan length and trials
  add almost nothing once those two are known.
- The two combine: at the first renewal, manual payers churn 37.3% of the
  time and auto-renewers 6.9%. By the 13th payment it's 6.5% against 2.1%.
- **Caveat:** this is observational. People who choose to pay manually may be
  less committed to begin with, and no regression can fully rule that out.
  The next check gets closer to it.

### Is it the person or the payment setup?

Take monthly subscriptions that started with two payments on the same setup,
and look at what happened after the third payment changed it, or didn't.
Third payments with periods ending March 2015 – September 2016.

| First two payments | Third payment | Subscriptions | Churned by the 5th payment |
|---|---|---|---|
| Manual | Switched to auto-renew | 3,761 | **10.2%** |
| Manual | Stayed manual | 167,986 | **37.1%** |
| Auto-renew | Switched to manual | 1,694 | 36.5% |
| Auto-renew | Stayed on auto-renew | 921,967 | 5.6% |

- **Churn follows the new setup, in both directions.** People who moved to
  auto-renew started to churn like auto-renewers, and people who moved to
  manual started to churn like manual payers.
- **The switchers weren't simply the keener users.** Before switching, manual
  payers who moved to auto-renew listened slightly less than those who stayed
  (18.5 vs 19.5 active days in four weeks). People who moved to manual listened
  more than those who stayed on auto-renew (17.4 vs 11.7), and still churned
  far more.
- At the same listening level before the switch, manual payers who switched
  churned 8–18% by the fifth payment, against 33–60% for those who stayed.
  The 1,281 who kept the same payment method and only changed the setting
  churned 10.0%.
- **Caveat:** switching is still a choice, and the switcher groups are small.
  This makes "the setup itself matters" much more likely, but only a test can
  prove it.

## 4. Are newer customers worse than older ones?

- **The channel mix changed a lot.** Channel 4 went from 0% of new paying users
  in early 2015 to 25% in early 2016 and 30% in early 2017. Channel 7 fell from
  56% (late 2015) to 46%.
- **Channels retain very differently.** 12 months after the first payment
  (cohorts Sep 2015 – Feb 2016): channel 7 keeps 86%, channel 9 57%, channel 4
  53%, channel 3 52%.
- **Retention slipped only because of the mix.** Month-3 retention fell from
  85.0% (cohorts Jul–Nov 2015) to 83.7% (Jul–Nov 2016). The shift toward
  channel 4 alone cost 3.8 points; within the channels, retention actually
  improved by 1.2 points.
- Together with question 3: channel 4's weak retention comes from how its users
  pay. Half of its new users start on a free trial, and three in four first
  renewals in channels 3, 4 and 9 are manual. In channel 7 almost none are.

## 5. Does listening warn us before someone leaves?

Monthly-plan renewal decisions in 2016, with listening in the 4 weeks before
the period ended.

| Active days in the 4 weeks before renewal | Share of decisions | Churn, auto-renew | Churn, manual |
|---|---|---|---|
| 0 | 22% | 4.2% | **79.2%** |
| 1–7 | 17% | 2.7% | 41.7% |
| 8–14 | 15% | 1.7% | 27.7% |
| 15–21 | 18% | 1.3% | 19.3% |
| 22–28 | 28% | 1.0% | 10.3% |

- **Within each payment type, listening is a strong signal.** Across everyone
  it looks weak (4.5% churn for no listening, 3.0% for near-daily listening),
  because most silent subscribers are on auto-renew and keep paying.
- **A drop matters too.** Auto-renewers whose listening halved churn 3.4% of the
  time, against 1.3% for steady listeners.
- **Activation matters for manual payers.** Among new manual payers, 37% are
  still subscribed after 3 months if they didn't listen at all in their first
  14 days, against 70% if they listened on 11–14 of them. For auto-renew payers
  it's 87% against 95%.
- **Not an artefact of the billing-gap rule.** Leaving out renewals that went
  through a billing gap changes these rates by 0.1 points at most.
- **Listening alone won't catch most churn.** Churners are spread across all
  listening levels: 24% hadn't listened at all, 21% listened almost every day.
- **Leave silent auto-renewers alone** until it's tested. 22% of renewal
  decisions come from people who didn't listen for four weeks and mostly still
  pay. A "we miss you" message could remind them to cancel.

## 6. Who comes back, and is it worth it?

Paid subscribers who churned between July 2015 and June 2016 (440,923):

- 20% pay again within 90 days, 31% within 180 days, 35% within 270 days.
  When they come back, the median gap is 83 days.
- **How it ended matters most.** 88% of people whose auto-renew payment just
  stopped (no cancel) are back within 180 days. 38% of manual payers who didn't
  renew come back, but only 10% of people who cancelled.
- Long-standing subscribers who leave (13+ payments) rarely return: 14%.
- **Returning subscribers are worth less.** In their first year they bring in
  NT$817 against NT$1,134 for a brand-new subscriber, and 69% of them make it
  through their first renewal against 89%.

## Recommendation

**Get manual payers onto auto-renew, starting at checkout for new subscribers
in channels 3, 4 and 9.**

Why there:

- These channels bring about 13,600 new paying subscribers a month, and 76% of
  them pay manually. At the first renewal, manual payers churn 34% of the time
  and auto-renewers 5%. That's about 3,500 subscribers a month lost at the
  first renewal, from this group alone.
- Across all tenures, manual renewals lose about 22,000 subscribers a month:
  57% of all churn in 2016.

This is not a promise of lower churn by some percentage. The switcher
comparison suggests much of the gap between manual and auto-renew payers comes
from the setup itself, but it's still observational. The test shows how much.

### How to test it

- **Change:** auto-renew switched on by default at checkout (easy to switch off),
  for new subscribers in channels 3, 4 and 9. Control: today's checkout.
- **Primary metric:** share of subscribers who churn at their first renewal
  (membership lapses for more than 30 days after the first paid period).
  Baseline about 27%.
- **Smallest effect worth detecting:** 2 points (27% → 25%).
- **Sample:** about 7,548 subscribers per group (two-sided 5% significance,
  80% power). That's 1.1 months of new subscribers in these
  channels, plus about 45 days until the first renewal outcome is known.
- **Guardrails:** checkout conversion (a default can put people off), refunds
  and complaints, cancellations in the first 7 days, and how many people switch
  auto-renew off.
- **Traps to avoid:** don't stop early when the numbers look good, randomise
  by user, and wait for the 30-day grace window to close before reading the
  result.

### Smaller ideas, to test later

- **Reminder with one-click renewal** a few days before expiry, for manual
  payers who've gone quiet. Manual payers with 0–7 active days in the last four
  weeks churn 42–79% of the time. A test on manual payers at any tenure
  (baseline about 20%) needs about 5,987 per group to detect a 2-point drop.
- **Offer existing manual payers a switch to auto-renew.** Same idea as the
  main test, for the existing base.
- **A payment-failure flow** for auto-renewers whose payment stops. Most of them
  come back on their own, so the aim is to shorten the gap, not to win them back.

## Caveats

- The data is from 2015–2017, and channel and payment-method codes are anonymised.
- Everything in question 3 is observational. The regression has a pseudo R² of
  0.19: payment type and tenure explain a real share of churn, not all of it.
- New-user analyses use users with a member record who registered from 2015 on.
  18% of paying users have no member record and are left out of those.
- The billing-gap rule uses listening. Question 5 was checked without it.
