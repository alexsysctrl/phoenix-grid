"""The siting dockets that touch this part of the valley, read out of the Commission's own hearing calendar.

A transmission project in Arizona does not become real by being announced; it becomes real by being applied for. The
Arizona Power Plant and Transmission Line Siting Committee is where that happens (A.R.S. 40-360 et seq.), and the
Commission's own hearings page lists every case it has noticed: docket number, project name, hearing date, and the
room the hearing was held in. This script reads that page — saved here as `source-acc-siting-hearings.html` —
pulls the case list out of it, and flags the cases whose geography or parties touch the West Valley: Avondale,
Buckeye, Goodyear, Tolleson, Litchfield Park, El Mirage, the Harquahala Valley, Gila Bend, the Marigold area.

Why this matters next to the utility filings: the annual report and the board minutes describe a programme. A docket
describes a specific line, with an applicant, a route described in a public record, and a date someone testified
about it. Case No. 248 was heard *in Avondale* — the transcript of that hearing is filed as
`source-ls248-harquahala-transcript-vol1.pdf` and is the nearest siting proceeding to the neighbourhood this project
is about. That is the kind of fact a forecast cannot produce.

Extraction is deliberately blunt: strip the page to text, cut at each "Case No." marker, take the docket identifier
that appears in that chunk (the Commission's format is L-<5 digits><letter>-<yy>-<mmdd>-<5 digits>), and keep the
first part of the chunk as the notice's own words. Where a chunk carries no project name in parentheses, the record
says so rather than inventing one. One known leak: rows are cut at the next case marker, so the *following* row's
docket can appear in a chunk — that is why the primary docket is kept apart from the others, and why the count of
others is a signal for agenda entries rather than a mistake to hide. The West Valley flag is a place-name match over the chunk, and the place names
it matched are recorded per case so a reader can see why a case was flagged.

Run:  python3 acc_siting.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from html import unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source-acc-siting-hearings.html"

DOCKET = re.compile(r"L-\d{5}[A-Z]-\d{2}-\d{4}-\d{5}")
CASE = re.compile(r"Case No\.\s*(\d{3})")
NAME = re.compile(r"\(\s*([^()]{4,90}?)\s*\)")
TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")

# The places this project is about, plus the geography a West Valley line would plausibly cross.
NEAR = ["Avondale", "Buckeye", "Goodyear", "Tolleson", "Litchfield Park", "El Mirage", "Harquahala",
        "Gila Bend", "Marigold", "Avalon", "Canyon Lake", "Buckeye Valley", "Estrella", "Surprise",
        "Alamar", "Broadway", "Cotton Corridor", "Rudd", "Gila River", "Grantsville", "Ajo", "Palo Verde"]
# A hearing held in a ZIP is a stronger fact than a place name mentioned in prose: it is where the room was.
STUDY_ZIPS = ["85323", "85353", "85338", "85342", "85334", "85037", "85041", "85043", "85051", "85374", "85379"]
ADDRESS = re.compile(r"\d{3,6}\s+[A-Za-z][A-Za-z0-9 .'-]{3,45},\s+[A-Za-z][A-Za-z ,' -]{2,28},\s*AZ\s*\d{5}")
UTILITIES = ["APS", "Arizona Public Service", "Salt River Project", "SRP", "TEP Southwest"]


def read_page(path: Path = SOURCE) -> str:
    return unescape(TAGS.sub(" ", path.read_text(encoding="utf-8", errors="ignore")))


def cases(text: str) -> list[dict]:
    """One record per 'Case No. NNN' chunk on the page, carrying its docket and the notice's own words."""
    marks = list(CASE.finditer(text))
    out: list[dict] = []
    seen: set[tuple[str, str | None]] = set()
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = WS.sub(" ", text[m.start():end]).strip()
        case = m.group(1)
        # The Commission's table puts the docket link immediately before the case number in the same cell, and the
        # notice text after it. So the paired docket is the nearest one *behind* the marker, and anything forward
        # belongs to this notice too. Looking only forward picks up the following row's docket instead.
        back = text[max(0, m.start() - 400):m.start()]
        prior = [(mm.start(), mm.group(0)) for mm in DOCKET.finditer(WS.sub(" ", back))]
        before = [d for _, d in sorted(prior, key=lambda t: -t[0])[:1]]
        dockets = sorted(set(before) | set(DOCKET.findall(chunk)))
        paren = NAME.search(chunk[len(m.group(0)):])
        name = paren.group(1).strip() if paren else None
        if name in {"_", ""}:
            name = None
        key = (case, dockets[0] if dockets else None)
        if key in seen:
            continue
        seen.add(key)
        near = sorted({p for p in NEAR if p.lower() in chunk.lower()})
        util = sorted({u for u in UTILITIES if re.search(rf"\b{re.escape(u)}\b", chunk)})
        dates = sorted(set(re.findall(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d\d\b", chunk)))
        venues = sorted(set(ADDRESS.findall(chunk)))
        zips = sorted(set(re.findall(r"\bAZ\s*(\d{5})\b", chunk)) | set(re.findall(r"\b(85\d{3})\b", chunk)))
        out.append({"case": case, "project": name, "primary_docket": before[0] if before else None,
                    "other_dockets_mentioned": [d for d in dockets if d != (before[0] if before else None)],
                    "near_west_valley": near, "utilities_named": util, "dates_in_notice": dates,
                    "venues_named": venues, "zips_in_notice": zips,
                    "hearing_in_a_studied_zip": sorted(set(zips) & set(STUDY_ZIPS)),
                    "notice_excerpt": chunk[:700]})
    for r in out:
        r["kind"] = classify(r)
    return out


AGENTS = re.compile(r"^[“\"']?(ACC|Commission|ACC or Commission|Arizona Corporation Commission)[”\"']?$")


def classify(row: dict) -> str:
    """A real application with a project name, or an agenda/minutes entry that aggregates many cases.

    The Commission's page contains both. Two signals separate them cleanly. Legal drafting writes 'the “ACC”'
    mid-sentence, which a parenthesis search cannot tell from a project name, so an institutional alias means
    agenda. And a notice for one application names one docket and one hearing; a minutes entry carries dozens of
    each. The thresholds are generous (three dockets, six hearing dates) because the difference in this document is
    between one and twenty, not between two and four.
    """
    if not row["primary_docket"]:
        return "agenda"
    if row["project"] is None or AGENTS.match(row["project"].strip()):
        return "agenda"
    if len(row["other_dockets_mentioned"]) > 2 or len(row["dates_in_notice"]) > 6:
        return "agenda"
    return "project"


WEST_VALLEY_PROJECTS = ["Harquahala North", "Marigold", "Cactus Flower", "Project Baccara", "Agua Fria"]


def selftest() -> None:
    text = read_page()
    rows = cases(text)
    # known-true: the case this project already has a transcript for must be in the page's own list, with its docket.
    harq = next((r for r in rows if r["case"] == "248"), None)
    assert harq is not None, "Case No. 248 is on the Commission's hearings page and this extractor did not find it"
    assert harq["primary_docket"] == "L-21304A-25-0169-00248", f"the filed docket is not the one paired to the case: {harq['primary_docket']}"
    assert harq["project"] and "Harquahala" in harq["project"], f"the project name was not read: {harq['project']!r}"
    assert harq["hearing_in_a_studied_zip"] == ["85323"], \
        f"the Case 248 hearing is noticed at a venue in Avondale 85323; the extractor read {harq['zips_in_notice']}"
    # known-true: at least one case names a utility, and the count is a real calendar, not a fragment.
    assert len(rows) >= 15, f"only {len(rows)} cases extracted from a hearings calendar"
    assert any(r["utilities_named"] for r in rows), "no utility is named in any notice, which is not true of this page"
    # the page mixes applications with agenda entries; the extractor has to tell them apart, not call both projects
    assert all(r["kind"] in {"project", "agenda"} for r in rows), "a case was not classified"
    assert harq["kind"] == "project", "the Harquahala case must classify as an application"
    assert any(r["kind"] == "agenda" for r in rows), "this page does contain agenda entries; none were classified"
    assert harq["other_dockets_mentioned"] == ["L-00000D-25-0154-00247"], \
        "the neighbouring table row's docket leaking into this chunk is a known limit of cutting at case markers; if it changed, the chunking changed"
    assert next((r for r in rows if r["case"] == "238"), {}).get("kind") == "agenda", \
        "a minutes entry naming 25 dockets is not an application"
    assert all(not (r["project"] and AGENTS.match(r["project"].strip())) for r in rows if r["kind"] == "project"), \
        "an institutional alias was read as a project name"
    assert "L-99999A-25-0169-00248" not in {d for r in rows for d in ([r['primary_docket']] + r['other_dockets_mentioned']) if d}, "the extractor produced a docket that is not on the page"
    # known-false: a docket and a case number that do not exist on the page must not be invented.
    all_dockets = {d for r in rows for d in ([r["primary_docket"]] + r["other_dockets_mentioned"]) if d}
    assert "L-99999A-25-0169-00248" not in all_dockets, "the extractor produced a docket that is not on the page"
    assert next((r for r in rows if r["case"] == "999"), None) is None, "a case number was invented"
    flagged = [r for r in rows if (r["near_west_valley"] or r["hearing_in_a_studied_zip"]) and r["kind"] == "project"]
    assert any(any(w in (r["project"] or "") for w in WEST_VALLEY_PROJECTS) for r in flagged), \
        "none of the known West Valley projects were found"
    print(f"self-test passed: {len(rows)} cases read from the Commission's own page, {len(flagged)} touching this "
          f"geography, Case No. 248 matched to its filed docket and its Avondale hearing")


if __name__ == "__main__":
    selftest()
    text = read_page()
    rows = cases(text)
    flagged = [r for r in rows if r["near_west_valley"] and r["kind"] == "project"]
    out = {
        "source": {
            "title": "Arizona Power Plant and Transmission Line Siting Committee — hearings and meetings calendar",
            "url": "https://www.azcc.gov/arizona-power-plant/hearings-and-meetings",
            "kept_as": SOURCE.name,
            "statute": "A.R.S. 40-360 et seq.; A.A.C. R14-3-201 to R14-3-220",
            "read_on": date.today().isoformat(),
        },
        "cases": rows,
        "flagged_for_this_area": [r["case"] for r in flagged],
    }
    (HERE / "acc_siting.json").write_text(json.dumps(out, indent=2))
    projects = [r for r in rows if r["kind"] == "project"]
    print(f"{len(rows)} calendar entries: {len(projects)} applications and {len(rows) - len(projects)} "
          f"agenda/minutes entries. {len(flagged)} applications touch this geography.")
    for r in sorted(flagged, key=lambda r: int(r["case"])):
        print(f"  Case {r['case']}: {r['project']}")
        print(f"      docket {r['primary_docket']}  |  places named: {', '.join(r['near_west_valley']) or '(none)'}")
        if r["venues_named"]:
            print(f"      venues named in the notice: {'; '.join(r['venues_named'])}")
        if r["hearing_in_a_studied_zip"]:
            print(f"      hearing held in a ZIP this project studies: {', '.join(r['hearing_in_a_studied_zip'])}")
        if r["utilities_named"]:
            print(f"      utilities named: {', '.join(r['utilities_named'])}")
        if r["dates_in_notice"]:
            print(f"      dates: {', '.join(r['dates_in_notice'])}")
        if r["other_dockets_mentioned"]:
            print(f"      other dockets in the same notice: {len(r['other_dockets_mentioned'])}")
