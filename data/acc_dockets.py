"""What the Commission actually decided, read out of its own docket system.

`acc_siting.py` reads the hearing calendar: it tells you what was applied for and when someone was invited to
testify. This script answers the other question — **what happened**. The Commission runs eDocket
(https://edocket.azcc.gov), whose back end is a JSON API at `efiling.azcc.gov/api/edocket/`; every docket there
carries its status and, for decided cases, the decision record: decision number, decision type, date.

Why the API and not the web page: the eDocket site is an Angular app and its search form is the only way into it
through a browser. The API it calls is public, unauthenticated, and stable enough to script against, and a JSON
record can be kept whole. The endpoint names came from reading the app's own bundle (`main.*.js`):
`searchByDocketDetailRequest` (POST), `docket/{docketID}` (GET), `GetDocketVotes/{docketID}` (GET). Note the two
identifier kinds — a *docket number* is a public label like L-21304A-25-0169-00248, a *docketID* is an internal
integer; the detail and votes endpoints only take the integer, which is why a lookup is two steps.

The input is the docket list already produced by `acc_siting.py` (`acc_siting.json`), so this reads outcomes for
the same cases the calendar showed, not for an unrelated set. Raw responses are written to `raw/` untouched:
a claim about a decision should be checkable against the bytes the Commission served.

Run:  python3 acc_dockets.py            # fetches everything in acc_siting.json, writes acc_dockets.json
      python3 acc_dockets.py --self-test
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / "acc_siting.json"
OUT = HERE / "acc_dockets.json"
RAW = HERE / "raw"
API = "https://efiling.azcc.gov/api/edocket/"
# Their edge answers a plain urllib UA inconsistently; a browser-like UA is what the app itself sends.
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36",
      "Accept": "application/json"}
SEARCH_BODY = {
    "companyID": None, "entityName": None, "docketID": None, "yearMatter": None, "docketTypeID": None,
    "documentID": None, "caseTypeID": None, "docketStatusID": None, "docketNumber": None,
    "searchAsString": True, "descriptionContains": None, "docketDateSearchFrom": None,
    "docketDateSearchTo": None, "currentPageIndex": 0, "rowsPerPage": 500, "rowsToSkip": 0,
}


def raw_name(path: str, body: dict | None) -> str:
    """A stable filename for the bytes of one response. `hash()` is randomised per process, which made every run
    write new files instead of replacing the ones from the last run — evidence that piles up by accident is not a
    record. Detail and votes endpoints are named by the docket id they were asked for; a search is named by the
    fields that produced it."""
    if "/" in path:
        base, ident = path.split("/", 1)
        return f"{base}_{ident}.json"
    parts = [f"{k}={v}" for k, v in sorted((body or {}).items()) if v not in (None, False, 0)]
    safe = "_".join(re.sub(r"[^A-Za-z0-9=-]", "_", part) for part in parts) or "no-terms"
    return f"search_{safe}.json"


def api(method: str, path: str, body: dict | None = None, tries: int = 3):
    """One call to the Commission's docket API. Retries are for the network, not for a 400 — a 400 is my error."""
    url = API + path
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                        headers={**UA, "Content-Type": "application/json"}, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode(errors="replace")
            RAW.mkdir(exist_ok=True)
            (RAW / raw_name(path, body)).write_text(raw)
            return json.loads(raw)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1:
                print(f"  failed {method} {path}: {e}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


def find_docket(docket_number: str) -> dict | None:
    """Resolve a public docket number to the record carrying its internal docketID."""
    body = dict(SEARCH_BODY, docketNumber=docket_number)
    data = api("POST", "searchByDocketDetailRequest", body)
    if not isinstance(data, dict):
        return None
    hits = [d for d in (data.get("searchResult") or []) if d.get("docketNumber") == docket_number]
    return hits[0] if hits else None


def decisions(docket_id: int) -> list[dict]:
    data = api("GET", f"GetDocketVotes/{docket_id}")
    if not isinstance(data, list):
        return []
    out = []
    for v in data:
        # An agenda item can carry a vote record with no decision behind it (a dissent, a procedural action).
        # Those are not decisions and must not be counted as one; they are counted separately, not dropped.
        if v.get("decisionNumber") is None:
            out.append({"decision_number": None, "procedural_record": True,
                        "agenda_id": v.get("agendaID"), "agenda_item_id": v.get("agendaItemID")})
            continue
        out.append({
            "decision_number": v.get("decisionNumber"),
            "decision_type": v.get("decisionCodeDescription"),
            "decision_date": (v.get("decisionDate") or "")[:10] or None,
            "agenda_id": v.get("agendaID"),
            "agenda_item_id": v.get("agendaItemID"),
        })
    return out


def status_of(docket_id: int) -> tuple[str | None, str | None]:
    """The docket's own status string and its filed date — the detail endpoint, not the search snippet."""
    data = api("GET", f"docket/{docket_id}")
    if not isinstance(data, dict):
        return None, None
    status = (data.get("docketStatus") or {}).get("value")
    return status, data.get("filedDate")


def case_of_docket(docket_number: str) -> str | None:
    """The case number a docket number itself states. The Commission's format ends in a five-digit case field
    (L-21304A-25-0169-00248 is Case 248), which is authoritative in a way that the hearing-calendar row that
    happened to mention the docket is not — `acc_siting.py` documents that a notice chunk can carry the *next*
    row's docket, so a calendar association is not a fact about the case."""
    tail = docket_number.rsplit("-", 1)[-1]
    return str(int(tail)) if tail.isdigit() else None


def record(docket_number: str, note: dict, primary: bool) -> dict:
    hit = find_docket(docket_number)
    rec = {
        "docket_number": docket_number,
        "case": case_of_docket(docket_number),
        "calendar_case_mentioned_under": note.get("case"),
        "project": note.get("project"),
        "primary_docket_for_that_case": primary,
        "in_calendar": True,
        "west_valley_places_named": note.get("near_west_valley") or [],
        "zips_in_notice": note.get("zips_in_notice") or [],
        "found_in_edocket": hit is not None,
        "company": (hit or {}).get("companyName"),
        "docket_type": (hit or {}).get("docketType"),
        "description": (hit or {}).get("description"),
    }
    if hit and hit.get("docketID"):
        rec["docket_id"] = hit["docketID"]
        rec["status"], rec["filed_date"] = status_of(hit["docketID"])
        all_records = decisions(hit["docketID"])
        rec["decisions"] = [d for d in all_records if d.get("decision_number") is not None]
        rec["procedural_records"] = len(all_records) - len(rec["decisions"])
        rec["decided"] = bool(rec["decisions"])
    time.sleep(0.3)
    return rec


# Dockets named by a source other than the hearing calendar. Each entry says where it came from, because the
# ledger is read as evidence about this corridor and a reader should be able to see how a case entered it.
# These three are the earlier Harquahala approvals named on the applicant's own project page (harquahalasun.com),
# kept in `source-harquahala-sun-project-page.html`; resolving them here is what turns those claims into the
# Commission's own decision records with dates.
EXTRA_DOCKETS = [
    ("L-21185A-22-0072-00201", "named on the applicant's project page as an approved Harquahala gen-tie"),
    ("L-21185A-22-0273-00211", "named on the applicant's project page as an approved Harquahala gen-tie"),
    ("L-21304A-24-0098-00231", "the Harquahala Sun Expansion (Phase V) gen-tie application"),
]


def run() -> dict:
    calendar = json.loads(INPUT.read_text())
    seen: dict[str, dict] = {}
    for note in calendar["cases"]:
        # `acc_siting.json` keeps the docket a notice is *about* apart from ones merely mentioned in its text,
        # because a row is cut at the next case marker. Both are worth resolving; only the first is primary.
        named = [(note.get("primary_docket"), True)] + [(d, False) for d in (note.get("other_dockets_mentioned") or [])]
        for dn, primary in named:
            if dn and dn not in seen:
                print(f"docket {dn} (case {note.get('case')}{'' if primary else ', mentioned'}) ...")
                seen[dn] = record(dn, note, primary)
    for dn, why in EXTRA_DOCKETS:
        if dn not in seen:
            print(f"docket {dn} (from the applicant's page) ...")
            seen[dn] = record(dn, {"case": None, "project": None}, False) | {"entered_from": why}

    rows = sorted(seen.values(), key=lambda r: (int(r["case"]) if (r.get("case") or "").isdigit() else 0,
                                                r["docket_number"]))
    decided = [r for r in rows if r.get("decided")]
    out = {
        "source": {"system": "Arizona Corporation Commission eDocket", "api": API,
                   "retrieved": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "input": "acc_siting.json (the Commission's own hearing calendar)"},
        "note": ("A docket that is not found here is not a docket that does not exist: the hearing calendar and the "
                 "docket system are separate publications, and some calendar rows are agenda items without a filed "
                 "docket. Decisions listed are the Commission's own records with decision numbers."),
        "cases": rows,
        "summary": {"dockets_queried": len(rows), "found": sum(1 for r in rows if r["found_in_edocket"]),
                    "with_decisions": len(decided)},
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT}: {out['summary']}")
    for r in rows:
        if not r["found_in_edocket"]:
            print(f"  case {r['case']} {r['docket_number']} -> not found in eDocket")
            continue
        for d in r["decisions"]:
            print(f"  case {r['case']} {r['docket_number']} {(r.get('company') or '')[:38]:38s} "
                  f"-> Decision {d['decision_number']} {d['decision_date']} ({d['decision_type']}) "
                  f"status: {r.get('status')}")
    return out


def self_test() -> int:
    fails = []
    # known-true: the Harquahala North docket (Case 248) was decided, and the record carries a decision number.
    hit = find_docket("L-21304A-25-0169-00248")
    if not hit or not hit.get("docketID"):
        fails.append("Case 248 docket not found in eDocket")
    else:
        decs = decisions(hit["docketID"])
        nums = {d["decision_number"] for d in decs}
        if 81564 not in nums:
            fails.append(f"Case 248 decisions do not include 81564, got {sorted(nums)}")
        match = next((d for d in decs if d["decision_number"] == 81564), None)
        if not match or match["decision_date"] != "2025-11-21":
            fails.append(f"Decision 81564 date wrong: {match}")
        if match and "Certificate of Environmental Compatibility" not in (match["decision_type"] or ""):
            fails.append(f"Decision 81564 type unexpected: {match['decision_type']}")
    # known-false: a docket number that does not exist must return nothing, not a guess.
    bogus = find_docket("L-99999Z-99-9999-99999")
    if bogus:
        fails.append(f"bogus docket matched something: {bogus}")
    # the ledger the report reads must be present and must contain the decided case
    if OUT.exists():
        led = json.loads(OUT.read_text())
        row = next((r for r in led["cases"] if r["docket_number"] == "L-21304A-25-0169-00248"), None)
        if not row or not row.get("decided"):
            fails.append("acc_dockets.json does not carry the decided Case 248 row")
    else:
        fails.append("acc_dockets.json missing — run the script before the self-test")
    print("acc_dockets self-test:", "FAIL " + "; ".join(fails) if fails else
          "PASS (Case 248 -> Decision 81564 2025-11-21 found; a false docket found nothing)")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    run()
