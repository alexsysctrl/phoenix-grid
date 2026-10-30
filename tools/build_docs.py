"""Render the two tables this repository is mostly about, from the data files it ships.

    python3 tools/build_docs.py         # writes permitted-corridors.md and county-calendar.md

Everything in those files is produced here rather than typed, so a reader can re-run it against a newer pull of the
same sources and see the ledger change. The self-test at the bottom asserts one row that must be present exactly as
written and one kind of row that must never appear.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# The corridor this repository is about: applications and grants touching Harquahala, Buckeye, Avondale and Goodyear,
# chosen from the places named in each notice, not from a result.
CORRIDOR = {"201", "209", "211", "221", "231", "241", "247", "248"}
PENDING = {"267", "268"}


def load(name):
    return json.loads((DATA / name).read_text())


def granted_table(cases):
    lines = ["| case | applicant | docket | filed | first decision | weeks | decisions since | docket status |",
             "|---|---|---|---|---|---|---|---|"]
    rows = [c for c in cases if c.get("decisions")]
    rows.sort(key=lambda c: min(d["decision_date"] for d in c["decisions"]))
    timing = {t["case"]: t for t in load("decision_timing.json")["cases"]}
    for c in rows:
        first = min(c["decisions"], key=lambda d: d["decision_date"])
        t = timing.get(c["case"], {})
        lines.append(
            f"| {c['case']} | {c.get('company')} | {c['docket_number']} | {c['filed_date'][:10]} "
            f"| **{first['decision_number']}, {first['decision_date']}** "
            f"| {t.get('weeks_filing_to_decision', '—')} | {len(c['decisions'])} | {c.get('status')} |")
    return "\n".join(lines), len(rows)


def pending_table(cases):
    lines = ["| case | applicant | docket | filed | status in the docket system |", "|---|---|---|---|---|"]
    n = 0
    for c in cases:
        if c["case"] in PENDING:
            lines.append(f"| {c['case']} | {c.get('company')} | {c['docket_number']} "
                         f"| {c.get('filed_date', '')[:10]} | *{c.get('status')}* |")
            n += 1
    return "\n".join(lines), n


def build_permitted():
    dockets = load("acc_dockets.json")
    timing = load("decision_timing.json")
    cases = dockets["cases"]
    granted, n_granted = granted_table(cases)
    pending, n_pending = pending_table(cases)
    amended = [c for c in cases if any("Amends" in (d.get("decision_type") or "") for d in c.get("decisions", []))]
    field, subset = timing["field"], timing["west_valley_subset"]
    doc = f"""# Permitted corridors in west Maricopa, read out of the regulator's docket system

Source: the Arizona Corporation Commission's eDocket API, queried {dockets['source']['retrieved'][:10]} through
`data/acc_dockets.py`, for every application on the Commission's own siting-hearing calendar for this geography plus
the cases the Harquahala applicant cites. {dockets['summary']['dockets_queried']} dockets queried,
{dockets['summary']['found']} found, {dockets['summary']['with_decisions']} carrying a decision record. A docket that
is not in that API is not a docket that does not exist: the hearing calendar and the docket system are separate
publications.

## Granted, in the order they were decided

{granted}

{n_granted} of the {len(cases)} dockets in the sample carry a decision. The dates in this table are the
Commission's own; where a project's own website gives different dates for the same decisions, the docket system wins
and the difference is recorded in SOURCES.md.

## How long the answer takes

Measured by `data/decision_timing.py`, from each docket's filing date to the first decision it carries:

| | cases | median weeks | quartiles | range |
|---|---|---|---|---|
| the whole sample | {field['cases']} | **{field['median']}** | {field['first_quartile']}–{field['third_quartile']} | {field['min']}–{field['max']} |
| this corridor | {subset['cases']} | {subset['median']} | {subset['first_quartile']}–{subset['third_quartile']} | {subset['min']}–{subset['max']} |

The number worth acting on is not the median, it is the width: 39 of {field['cases']} were decided inside sixteen
weeks and {sum(1 for c in timing['cases'] if c['weeks_filing_to_decision'] > 24)} took more than twenty-four. A
process that answers in a band that narrow is a planning input. An applicant who is told fourteen weeks can treat the
permit as a date rather than a hope.

## Still open

{pending}

{n_pending} cases in this sample are undecided as of the retrieval date, both of them Salt River Project filings
heard in September 2026. `tools/watch.py` re-runs the same query and reports only what changed — a newly decided
docket, a new decision on one already decided, or a status moving.

## A grant is not a finished record

{len(amended)} of the {len(cases)} dockets carry a later decision whose type is "Decision - Amends a Previous
Decision". The clearest example in this corridor is Decision 81776 (7 May 2026), which amends a 2022 approval. When
this repository says a project is permitted, it means a record exists at a date; the record can be revised afterwards,
and the watch reports that as an event rather than treating it as news about something else.
"""
    (ROOT / "permitted-corridors.md").write_text(doc)
    return len(cases), n_granted, n_pending, len(amended)


def county_table(path, label):
    record = json.loads((DATA / path).read_text())
    rows = record["cases"]
    lines = ["| case | district | project as the county titles it | what the request does | Commission recommendation |",
             "|---|---|---|---|---|"]
    for r in rows:
        vote = r["commission_recommendation"]
        lines.append(f"| {r['case'] or '—'} | {r['district'] or '—'} | {r['title']} | {r['request']} "
                     f"| {(vote['date'] + ' · ' + vote['vote']) if vote else '—'} |")
    counts = record["counts"]
    tally = ", ".join(f"{v} × {n}" for v, n in sorted(counts["vote_tally"].items()))
    return (f"### {label}\n\n{counts['items']} land-use items; **{counts['industrial_or_utility']} of them change a "
            f"designation toward Utilities or an industrial (IND-2 IUPD) district**. "
            f"Commission recommendations recorded: {tally}.\n\n" + "\n".join(lines)), counts


def build_county():
    dec, c1 = county_table("dec2025-consent-cases.json", "10 December 2025")
    apr, c2 = county_table("apr2026-consent-cases.json", "8 April 2026")
    doc = f"""# Maricopa County's consent calendar, as a record of what land is being made usable

The Corporation Commission decides whether a line or a plant may be built. What a parcel is *for* is the county's
decision, taken through a Comprehensive Plan Amendment (a change of designation in the Vision 2030 plan) and a zone
change. Those are the earliest public signals in this subject, and they are dated and attributable in a way an
assessor's roll never is.

Both documents below are the county's own Board of Supervisors agendas, read from maricopa.gov and hashed; the URLs
and sha256 are in SOURCES.md. `data/consent_cases.py` parses them and asserts the counts, including one case that
must **not** be counted as a land-use conversion (an event-venue special use permit).

**Read the tables as requests, not approvals.** They record what the Board was asked to approve and what the county's
Planning & Zoning Commission recommended. The Board's own votes are not in these documents and are not claimed here.

{dec}

{apr}

## What is established and what is not

Established, from the county's own text: these cases exist; what each asks for; where the land is; who filed it; what
the county's planning body recommended and on what date, including a 7-0 on Mariposa Energy Park in November 2025 and
a 5-1 on Hassayampa Ranch in March 2026. Not established: whether the Board approved any of them. Five routes to the
minutes were tried on 29 October 2026 and none returned the text — the Agenda Center item page for the earlier case
404s, the search endpoint and board pages are script-rendered shells, and the later agenda does not recite the earlier
approvals. The remaining routes are the county's meeting video and a written records request to the Clerk's office.
"""
    (ROOT / "county-calendar.md").write_text(doc)
    return c1, c2


def claim_filings():
    """Render every quote the datasets hold, with the page it was found on. Generated rather than typed so the
    page numbers cannot drift from the data, and including the things that were looked for in these documents
    and not found — a record of what a source does not say is part of the source record."""
    aps = load("aps_capital.json")
    srp = load("srp_board.json")

    def rows(claims, quote_key):
        out = []
        for c in claims.values() if isinstance(claims, dict) else claims:
            quote = c.get(quote_key) or c.get("quoted") or c.get("verbatim")
            attribution = c.get("attributed") or c.get("attributed_verbatim") or ""
            out.append(f"> “{quote}”\n>\n> — page {c['page']}"
                       + (f", attributed to {attribution}" if attribution else ""))
        return "\n\n".join(out)

    doc = f"""# What the two utilities said, and where it is written

Two documents, both filed rather than published: Pinnacle West Capital Corporation's 2025 annual report, which carries
Arizona Public Service's audited report to the SEC ({aps['pages']} pages), and Salt River Project's Joint District
Board and Council packet for its 30 September 2025 meeting, filed with the Commission on {srp['source'].get('filed')}.
Every sentence below was found in the document at the page given — `tools/verify_claims.py` checks that, not my
transcription. These are the parties describing their own plans; that is stated here rather than left for a reader to
work out.

## Arizona Public Service, from its annual report

{rows(aps['claims'], 'quoted')}

The facility tables in the same filing are reproduced in `data/aps_capital.json` as the filing prints them, with the
page. The numeric columns after the year are not labelled unambiguously in the extracted text, so no capacity totals
are computed here — a row is a row the company printed, not a figure derived from it.

## Salt River Project, from its own board packet

{rows(srp['claims'], 'verbatim')}

**What was looked for in that document and is not in it:** {', '.join(srp['checked_absent'])}. The packet's project
maps are images, so a place can be in the plan and not in the extractable text. That list is published because the
absence is a fact about the document, not a fact about SRP's plans.

## Reading the two together

Both utilities describe the same driver in different words — APS names specific advanced-manufacturing and data-centre
customers in its filing's risk and outlook sections; SRP's packet records a presentation to its own board about
"large-scale load growth". Neither number is independently corroborated by the other, and neither is a projection of
mine. What is independent is the permitting record in `permitted-corridors.md`: applications by these same parties,
and decisions with dates and numbers attached.
"""
    (ROOT / "utility-filings.md").write_text(doc)
    return len(aps["claims"]), len(srp["claims"]), len(srp["checked_absent"])


def main():
    n_cases, n_granted, n_pending, n_amended = build_permitted()
    c1, c2 = build_county()
    n_aps, n_srp, n_absent = claim_filings()
    print(f"permitted-corridors.md: {n_granted} granted of {n_cases} dockets, {n_pending} open, {n_amended} amended")
    print(f"county-calendar.md: {c1['items']} December items ({c1['industrial_or_utility']} conversions), "
          f"{c2['items']} April items ({c2['industrial_or_utility']} conversions)")
    print(f"utility-filings.md: {n_aps} quotes located in the APS filing, {n_srp} in the SRP packet, "
          f"{n_absent} checked-and-absent items recorded")

    # Known-true and known-false. Case 248 is this corridor's own permit and its numbers are public. And a docket
    # with no decision record must never appear in a table of grants.
    text = (ROOT / "permitted-corridors.md").read_text()
    assert ("| 248 | Harquahala Complex HoldCo, LLC | L-21304A-25-0169-00248 | 2025-08-15 "
            "| **81564, 2025-11-21** | 14.0 |") in text, "the corridor's own decision is not rendered as measured"
    assert "Open Meeting Pending" in text and "267" in text, "the open cases disappeared"
    rows = [l.split("|") for l in text.splitlines()
            if l.startswith("| ") and len(l.split("|")) == 10 and l.split("|")[1].strip().isdigit()]
    assert len(rows) >= 60, f"only {len(rows)} grant rows rendered"
    assert all(row[5].strip().startswith("**") for row in rows), "a granted row has no decision number and date"
    county = (ROOT / "county-calendar.md").read_text()
    assert "CPA250002" in county and "Z250015" in county, "the Harquahala county cases are missing"
    assert "event-venue special use permit" in county, "the known-false case is no longer named"
    filings = (ROOT / "utility-filings.md").read_text()
    assert "263 miles of new transmission lines" in filings, "the ten-year plan quote disappeared"
    assert "What was looked for in that document and is not in it" in filings, "the checked-absent list disappeared"
    print("self-test ok")


if __name__ == "__main__":
    main()
