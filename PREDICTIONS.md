# What follows from the records, and what would show each of it is wrong

Four claims, ranked by how well the evidence in this repository supports them. Each one names the measurement that
would show it is wrong, because a claim without a falsifying test is just an opinion with citations. Where the data
went against what I expected, that is written into the claim rather than quietly dropped.

## 1. The build is not a forecast. It is filed, dated and partly decided.

**Confidence: high.** This is the strongest thing in the repository because it does not require predicting anything.

Arizona Public Service's 2026 Ten-Year Transmission Plan, printed in Pinnacle West's annual report to the SEC, projects
**263 new route-miles and 725 miles upgraded** against an existing network of **5,939 pole miles and 477 substations** —
4.4% new and 12.2% rebuilt, about 99 miles of work a year for ten years. The same filing records **$2.4 billion of
capital in 2025**, **more than 1,600 MW of new generation and battery storage deployed in one year**, peak demand up
more than 5%, and projected sales growth of **5 to 7% a year through 2030**, with the filing naming "Taiwan
Semiconductor Manufacturing Company, Microsoft, Amkor, SMC and others" as the surge behind it. Salt River Project told its own board that its network is 1,492 miles with 287 substations and that its
Integrated System Plan concludes it "will need to more than double, if not triple, resource capacity in the next
decade".

Those are plans by the parties doing the building. The permits are not plans. Of the 78 dockets this repository pulled
from the Commission's docket system, **67 carry a decision**; in this corridor the same developer holds two
Certificates of Environmental Compatibility (Decision 79467, 15 August 2024; Decision 81564, 21 November 2025), and at
least six more certificates were granted to other parties on the same geography in the same window.

**What would show this is wrong:** a denial, a narrowing, or a build that stops. All three are events the docket
records show — `tools/watch.py` re-runs the query and reports only what changed. Two cases in this sample are still
undecided (Salt River Project's 230 kV line and the Marigold thermal plant), and they are the nearest test.

## 2. Permitting here is fast in a way that can be planned around, but it is not unusually fast.

**Confidence: high, and it is a measurement rather than an impression.** For the 67 decided dockets, the interval from
filing to the first decision has a **median of 15.4 weeks**, first quartile 14.3, third quartile 16.7, range 11.0 to
87.0. Thirty-nine were decided inside sixteen weeks; two took more than twenty-four.

When this project first noticed that the Harquahala approvals came at fourteen weeks it read that as speed. It is not:
fourteen weeks is the middle of the distribution. What the numbers support is narrower and more useful — the process is
*tight*, with a band about two and a half weeks wide around its median across sixty-seven cases. A predictable
fourteen-to-seventeen weeks is a planning input. A fast average would not be, and neither would a slow one.

**What would show this is wrong:** a widening. Re-running `data/decision_timing.py` on a newer pull of the same API
gives the quartiles again; a shift in the interquartile range is the finding, not any single case.

## 3. Land near the build is *cheaper* per acre than land near an established neighbourhood, not dearer.

**Confidence: low, and the prediction that produced this is the one that failed.**

The expectation was that land at the edge of a named substation stops being edge land before houses move, because what
gets created is entitlement — services, zoning, a buyer — not a structure. The county's 2026 roll, read in 1 km
squares around Rudd substation (a 500 kV asset, half-owned by another utility), Orme substation, and an offset control
3.5 km away in the same ZIP with nothing named in any filing, says something else.

| within 1 km | houses, median assessed | median year built | the county's "AG / VACANT LAND" parcels | median parcel | median per acre | median lot |
|---|---|---|---|---|---|---|
| Rudd substation | $378,500 (1,152 parcels) | **2021** | **540 parcels** | **$7,500** | **$37,106** | 0.18 ac |
| Orme substation | $306,300 (1,238) | 2002 | 39 parcels | $219,600 | $430,112 | 1.51 ac |
| offset control | $243,000 (1,563) | **1963** | 245 parcels | $78,768 | **$476,639** | 0.18 ac |

Read the row that matters. The same legal class, the same median lot size — 0.18 of an acre — and the undeveloped
parcel beside the 500 kV substation is assessed at **$7,500** while the equivalent parcel inside an older neighbourhood
is assessed at **$78,768**. A factor of ten. The opposite of the prediction.

Two things follow. First, the house difference is not an infrastructure effect: the housing near Rudd has a median
build year of 2021 and the control's is 1963, so the raw medians compare new stock to old stock and nothing else.
Second, the cheap land beside the build is consistent with land that is *held before development* — the pattern of a
pipeline of new subdivisions where the raw parcels are valued as raw, in quantity (540 of them), rather than in
scarcity. The control's parcels are the other situation: small in-fill lots in a built-out area, priced as land you
cannot get again. That is a hypothesis about why the numbers look like this, and it is not measured.

The utility's own land is visible in the same roll: four parcels the county classes as **GAS AND ELECTRIC** within
1 km of Rudd, averaging 18.5 acres at a median assessed $3,678,250 each.

**What would show this wrong, or make it a finding:** the same comparison at more points and over time. One baseline
per point, one assessment year, and two comparison groups of 39 and 54 parcels is not enough to say anything about how
land behaves; it is enough to say the simple version of the prediction does not survive contact with it. The repeatable
version is in the repository: run `data/monitor.py` again next assessment cycle and it reports the change against the
stored baseline, with the negative control (a point in Colorado, which must contain zero Maricopa parcels) checked in
the same self-test.

## 4. What land is being made usable is visible at the county a year before ground moves

**Confidence: medium.** The Corporation Commission decides whether a line or plant may be built. What a parcel is *for*
belongs to the county, through a Comprehensive Plan Amendment and a zone change. Those are dated, attributable to
specific parcels, and cheaper to read than any market signal.

The county's own Board agendas show the rate. On 10 December 2025 its Planning & Zoning consent calendar carried
**twelve land-use items, eight of which change a designation toward Utilities or an industrial (IND-2 IUPD) district**,
with the county's Planning & Zoning Commission recommending eleven of them — ten unanimously, one 7-0. Four months
later, on 8 April 2026, five more, three of them industrial conversions, including one that amends the *conditions* of
a 2023 industrial approval rather than asking for a new one, and one 5-1 recommendation on 2,040 acres. The Board's
own votes are not in those documents and are not claimed here.

**What would show this wrong:** a rejected item, or a designation change that is never followed by anything on the
ground. The first is checkable by reading the Board's action, which is the gap this repository states openly rather
than fills in; the second only by years of the same calendar.

## What this repository cannot say

There is one assessment year, so nothing here is a rate of change. The price evidence is the county's own recorded
last-sale-per-parcel data through the first quarter of 2025, which is not an index and drops a quarter of a ZIP's unsold
houses out of the comparison; a repeat-sales index (FHFA publishes one for this metro) is the instrument that would
make the price claims properly testable, and it is not here. The demand case behind the utility numbers is stated by
the utilities themselves — APS's own risk factors name the Arizona housing market and a slower data-centre ramp. And on
the county side, the strongest documents in this repository are agendas: requests and recommendations, not approvals.
