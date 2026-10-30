# Phoenix grid

A public record of what is being permitted, built and priced on the west side of the Phoenix metropolitan area, built
from primary documents: the Arizona Corporation Commission's own docket records, two utility filings, Maricopa County's
land-use agendas and parcel roll, and the Census Bureau.

The question it is trying to answer is concrete. A very large amount of electricity infrastructure is going into the
corridor west of Avondale and Buckeye — transmission lines, substations, generation and storage — and the things people
care about nearby (what land costs, what a house is worth, what gets built next) are decided on a schedule set by that
infrastructure. This repository tries to establish what is actually decided rather than what is announced, and then to
say what follows with the test that would show each claim is wrong.

It is maintained as a working record rather than an article: the datasets are produced by scripts that re-read the
sources, and one of those scripts reports what changed since the last time it ran.

By Alex, from SQOPA. Started October 2026.

## Start here

| file | what it is |
|---|---|
| [`PREDICTIONS.md`](PREDICTIONS.md) | four claims, each with its confidence, the evidence, and the measurement that would falsify it. Includes the one where the data disagreed with the prediction. |
| [`permitted-corridors.md`](permitted-corridors.md) | 67 permitted siting cases with applicants, docket numbers, filing and decision dates, elapsed time, and current docket status; the open cases; and how often a grant is later amended. |
| [`county-calendar.md`](county-calendar.md) | Maricopa County's Board land-use calendar for December 2025 and April 2026: what each case asks to change, where the land is, who filed it, and what the county's planning body recommended. |
| [`utility-filings.md`](utility-filings.md) | every sentence quoted from the two utility documents, with the page it was found on, and the things that were searched for in those documents and are not in them. |
| [`SOURCES.md`](SOURCES.md) | every source with its URL, the date it was fetched and its sha256, including the documents that are too large to ship. |
| `data/` | the derived datasets and the scripts that produce them, each script beside what it writes. |
| `decisions/` | 76 decision texts as the Commission publishes them, with an index carrying each one's document id. |
| `baselines/` | parcels inside 1 km and 2 km squares around two substations and a control point, with lot areas, construction years and the county's own land legal classes. |
| `tools/` | the document generator, the claim checker, and the docket watch. |

## The numbers that hold the record together

- **78 dockets** in the sampled corridor, **67 with a decision record**; the median interval from filing to the first
  decision is **15.4 weeks**, with a first-to-third quartile band of 14.3 to 16.7.
- **Eleven of those dockets carry a later decision that amends the original** — a permit is a record with a working life.
- One county agenda, on 10 December 2025, moved **eight land-use designations toward utility or industrial use in a
  single sitting**.
- APS's filed ten-year plan: **263 new route-miles and 725 upgraded** against a network of 5,939 pole miles and 477
  substations.
- The measurement that disagreed with my own expectation: an undeveloped 0.18-acre parcel the county classes as vacant
  land is assessed at **$7,500** within 1 km of a 500 kV substation, and at **$78,768** for the same legal class and
  lot size 3.5 km away in an established neighbourhood.

## Reproducing it

Python 3.10 or newer, standard library only. No packages, no API keys: everything here is read from public sources over
HTTPS.

```bash
python3 tools/verify_claims.py     # re-derive every number quoted in these documents from the shipped data
python3 tools/build_docs.py        # regenerate the three generated documents from the JSON
python3 data/acc_dockets.py        # re-query the Commission's docket API and rewrite the ledger
python3 data/decision_timing.py    # recompute the filing-to-decision distribution
python3 data/monitor.py            # re-read the parcel roll around the three points and report the deltas
python3 tools/watch.py             # re-run the docket query and report only what changed
```

Each script carries a self-test that asserts one thing it must find and one thing it must not. `verify_claims.py`
checks the documents against the data rather than against my arithmetic; if a number in a document is not derivable
from these files, it says so and fails.

## What this is not

It is not a market report and it is not advice. It is one assessment year of a parcel roll, one transcript volume, a
set of dockets chosen because they name this geography, and three utility or county filings, with the gaps named where
they are: the Board of Supervisors' own votes on the county cases are not in the records I could obtain, two siting
cases in this corridor are still undecided, and the price evidence is a series of recorded last sales rather than a
repeat-sales index. Where a claim rests on a company describing its own plans, that is said out loud.
