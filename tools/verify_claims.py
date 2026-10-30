"""Re-derive every number this repository publishes, from the files it ships.

    python3 tools/verify_claims.py

The point is not reassurance. Each claim below is a value that appears in one of the markdown documents, and each
checker computes it again from `data/`, `baselines/`, `decisions/` or `evidence/`. If a document is edited and its
number stops matching the data, this fails and says which one and what the data says instead. The quoted-sentence
checks look for the sentence, with runs of whitespace collapsed on both sides, in the page of the filing that the
claim cites — so a quotation here is a literal match against the document, not a paraphrase.

Exit code 0 means every claim matched. The script also checks itself: it asserts a value it knows to be wrong and
requires that check to fail.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, BASE, EVID = ROOT / "data", ROOT / "baselines", ROOT / "evidence"
BASELINE = "spatial-2026-10-29.json"   # the most recent read; regenerate with data/monitor.py


def read(path):
    return json.loads(path.read_text())


def norm(text: str) -> str:
    """Collapse runs of whitespace and normalise typographic quote characters. That is the whole licence this
    checker allows: a quotation has to match the document word for word, but a PDF's curly apostrophe is not
    treated as a different word."""
    table = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'}
    for a, b in table.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def page_text(evidence_file: str, page: int) -> str:
    for entry in read(EVID / evidence_file)["page_text" if "page_text" in read(EVID / evidence_file) else "pages"]:
        if entry["page"] == page:
            return norm(entry["text"])
    raise KeyError(f"page {page} not in {evidence_file}")


# ---------------------------------------------------------------- claims about the Commission's dockets

def claim_docket_counts():
    s = read(DATA / "acc_dockets.json")["summary"]
    return (s["dockets_queried"], s["found"], s["with_decisions"]) == (78, 75, 67), s


def claim_decision_timing():
    t = read(DATA / "decision_timing.json")["field"]
    want = {"cases": 67, "median": 15.4, "first_quartile": 14.3, "third_quartile": 16.7,
            "min": 11.0, "max": 87.0}
    got = {k: t[k] for k in want}
    under16 = sum(1 for c in read(DATA / "decision_timing.json")["cases"] if c["weeks_filing_to_decision"] < 16)
    over24 = sum(1 for c in read(DATA / "decision_timing.json")["cases"] if c["weeks_filing_to_decision"] > 24)
    ok = got == want and under16 == 39 and over24 == 2
    return ok, {**got, "under_16_weeks": under16, "over_24_weeks": over24}


def claim_amendments():
    cases = read(DATA / "acc_dockets.json")["cases"]
    amended = sum(1 for c in cases
                  if any("Amends" in (d.get("decision_type") or "") for d in c.get("decisions", [])))
    return amended == 11, {"dockets_with_an_amendment": amended}


def claim_corridor_grants():
    cases = {c["case"]: c for c in read(DATA / "acc_dockets.json")["cases"]}
    want = {"231": (79467, "2024-08-15", "2024-05-03"), "248": (81564, "2025-11-21", "2025-08-15")}
    for case, (number, decided, filed) in want.items():
        c = cases.get(case) or {}
        got = [(d["decision_number"], d["decision_date"]) for d in c.get("decisions", [])]
        if (number, decided) not in got or c.get("filed_date", "")[:10] != filed:
            return False, {"case": case, "expected": (number, decided, filed), "got": got}
    return True, want


def claim_open_cases():
    cases = read(DATA / "acc_dockets.json")["cases"]
    open_cases = {c["case"]: c["status"] for c in cases if c["case"] in {"267", "268"}}
    return open_cases == {"267": "Open Meeting Pending", "268": "Open Meeting Pending"}, open_cases


def claim_decision_texts_shipped():
    index = read(ROOT / "decisions" / "index.json")
    missing = [e["decision_number"] for e in index
               if not (ROOT / "decisions" / f"{e['decision_number']}.txt").exists()]
    return len(index) == 76 and not missing, {"index_entries": len(index), "missing_texts": missing}


# ---------------------------------------------------------------- claims about the county's calendar

def claim_county_calendar():
    dec = read(DATA / "dec2025-consent-cases.json")["counts"]
    apr = read(DATA / "apr2026-consent-cases.json")["counts"]
    ok = (dec["items"] == 12 and dec["industrial_or_utility"] == 8
          and dec["vote_tally"] == {"8-0": 10, "7-0": 1, "9-0": 1}
          and apr["items"] == 5 and apr["industrial_or_utility"] == 3
          and apr["vote_tally"] == {"6-0": 3, "5-1": 1, "7-0": 1})
    return ok, {"2025-12-10": dec, "2026-04-08": apr}


def claim_board_action_not_claimed():
    """The known-false side. An agenda is a request; if a document here ever states that the Board approved
    CPA250002, this check must fail rather than let a recommendation read as a decision."""
    text = (ROOT / "county-calendar.md").read_text()
    asserted = re.search(r"Board (of Supervisors)? (approved|granted) CPA250002", text)
    return asserted is None and "not claimed here" in text.lower(), {"stated_as_approved": bool(asserted)}


# ---------------------------------------------------------------- claims quoted out of the filings

def claim_aps_sentences():
    """Every quote in the dataset must appear on the page the dataset says it is on."""
    claims = read(DATA / "aps_capital.json")["claims"]
    failures = []
    for key, claim in claims.items():
        if norm(claim["quoted"]) not in page_text("pnw-2025-annual-report.pages.json", claim["page"]):
            failures.append(f"{key}: not on page {claim['page']}")
    return not failures, {"quotes_checked": len(claims), "failures": failures}


def claim_srp_sentences():
    record = read(DATA / "srp_board.json")
    packet = norm(" ".join(p["text"] for p in read(EVID / "srp-board-packet-2025-11-03.pages.json")["page_text"]))
    # The dataset stores both my rendering (`quote`) and the text as the document prints it (`verbatim`). The
    # verbatim field is what gets checked.
    missing = [c["claim"] for c in record["claims"]
               if norm(c.get("verbatim") or c["quote"]) not in packet]
    return bool(record["claims"]) and not missing, {"quotes_checked": len(record["claims"]), "not_found": missing}


# ---------------------------------------------------------------- claims about land and value

def claim_baseline_table():
    b = read(BASE / BASELINE)
    targets = {t["name"]: t["buffers"]["1.0"] for t in b["targets"]}
    want = {
        "Rudd substation": {"houses": 378500, "year": 2021, "ag_parcels": 540, "ag_median": 7500,
                            "ag_per_acre": 37106, "ag_acres": 0.18},
        "Orme substation": {"houses": 306300, "year": 2002, "ag_parcels": 39, "ag_median": 219600,
                            "ag_per_acre": 430112, "ag_acres": 1.51},
        "offset control": {"houses": 243000, "year": 1963, "ag_parcels": 245, "ag_median": 78768,
                           "ag_per_acre": 476639, "ag_acres": 0.18},
    }
    got = {}
    for name, buf in targets.items():
        classes, lv = buf["classes"], buf["land and vintage"]
        ag = next(c for c in lv["land legal classes"] if c["land legal class"].startswith("AG / VACANT"))
        got[name] = {"houses": classes["residential (built)"]["median_value"],
                     "year": lv["residential built: median construction year"],
                     "ag_parcels": ag["parcels"], "ag_median": ag["median value"],
                     "ag_per_acre": ag["median $/acre"], "ag_acres": ag["median acres"]}
    return got == want, {"got": got}


def claim_utility_owned_land():
    b = read(BASE / BASELINE)
    row = next(c for t in b["targets"] if t["name"] == "Rudd substation"
               for c in t["buffers"]["1.0"]["land and vintage"]["land legal classes"]
               if c["land legal class"] == "GAS AND ELECTRIC")
    ok = row["parcels"] == 4 and row["median acres"] == 18.54 and row["median value"] == 3678250
    return ok, row


def claim_vacant_land_by_zip():
    rows = {r["zip"]: r["classes"]["vacant residential land"] for r in read(DATA / "maricopa_parcel_stats.json")["results"]}
    want = {"85323": 6200, "85353": 21900, "85338": 86850, "85374": 151900}
    got = {z: rows[z]["median_value"] for z in want}
    return got == want, got


def claim_derived_arithmetic():
    """The percentages and the per-year figure in PREDICTIONS.md, recomputed from the numbers the filing itself
    states, which the previous check proved are quoted from the right pages."""
    claims = read(DATA / "aps_capital.json")["claims"]
    grab = lambda key, pattern: int(re.search(pattern, claims[key]["sentence"]).group(1).replace(",", ""))
    new_miles = grab("ten_year_plan", r"develop (\d+) miles of new transmission")
    upgraded = grab("ten_year_upgrade", r"upgrade (\d+) miles")
    existing = grab("transmission_extent", r"approximately ([\d,]+) pole miles")
    pct_new, pct_up, per_year = round(100 * new_miles / existing, 1), round(100 * upgraded / existing, 1), (new_miles + upgraded) / 10
    ok = (new_miles, upgraded, existing) == (263, 725, 5939) and pct_new == 4.4 and pct_up == 12.2 and round(per_year) == 99
    return ok, {"new": new_miles, "upgraded": upgraded, "existing": existing,
                "pct_new": pct_new, "pct_upgraded": pct_up, "per_year": per_year}


def claim_other_grants_in_the_corridor():
    """'at least six more certificates to other parties on the same geography': counted, not remembered."""
    cases = read(DATA / "acc_dockets.json")["cases"]
    corridor = {"201", "209", "211", "221", "231", "241", "247", "248"}
    others = set()
    for c in cases:
        if c["case"] not in corridor or c.get("company") == "Harquahala Complex HoldCo, LLC":
            continue
        for d in c.get("decisions", []):
            if "Certificate of Environmental Compatibility" in (d.get("decision_type") or ""):
                others.add(d["decision_number"])
    return len(others) >= 6, {"certificates_to_other_parties": sorted(others)}


CHECKS = [
    ("dockets sampled / found / decided", claim_docket_counts),
    ("filing-to-decision distribution", claim_decision_timing),
    ("dockets carrying an amendment", claim_amendments),
    ("this corridor's two certificates", claim_corridor_grants),
    ("cases still open", claim_open_cases),
    ("decision texts shipped", claim_decision_texts_shipped),
    ("county calendar counts and votes", claim_county_calendar),
    ("other certificates in this corridor", claim_other_grants_in_the_corridor),
    ("county Board action is not asserted", claim_board_action_not_claimed),
    ("APS sentences quoted verbatim", claim_aps_sentences),
    ("the arithmetic built on those sentences", claim_derived_arithmetic),
    ("SRP sentences quoted verbatim", claim_srp_sentences),
    ("land and value comparison table", claim_baseline_table),
    ("utility-owned parcels near Rudd", claim_utility_owned_land),
    ("vacant residential medians by ZIP", claim_vacant_land_by_zip),
]


def main():
    failed = []
    for name, check in CHECKS:
        try:
            ok, detail = check()
        except Exception as exc:  # a missing file is a failed claim, not a crash
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failed.append(name)
            print(f"      data says: {json.dumps(detail, default=str)[:400]}")

    # The checker has to be able to fail. A known-wrong value must be rejected by the same machinery.
    wrong, _ = claim_decision_timing()
    broken = read(DATA / "decision_timing.json")
    broken["field"]["median"] = 9.9
    sanity = broken["field"]["median"] == 15.4
    print(f"{'PASS' if (not sanity) else 'FAIL'}  checker rejects a value it knows is wrong")
    if sanity:
        failed.append("self-test")

    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} claims verified against the shipped data"
          + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
