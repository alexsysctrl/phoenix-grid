"""How long a Certificate of Environmental Compatibility takes, measured from the regulator's own dates.

The docket records carry a filing date and, for decided cases, every decision with its date. Subtracting the first
decision from the filing gives the thing a developer actually plans around: how long from application to an answer.

    python3 decision_timing.py            # reads acc_dockets.json, writes decision_timing.json

`acc_dockets.json` comes from `acc_dockets.py`, which queries the Arizona Corporation Commission's eDocket API for
every docket named in the Commission's own siting-hearing calendar for this geography, plus the cases the Harquahala
applicant cites. A docket with no decision is excluded rather than guessed at; a span that comes out negative is
reported as a data problem, not quietly dropped, because that would mean a decision predating its own application.
"""

import json
from datetime import date
from pathlib import Path
from statistics import mean, median, quantiles

HERE = Path(__file__).parent
SRC = HERE / "acc_dockets.json"
OUT = HERE / "decision_timing.json"

# The West Valley corridor this project is about, by case number: the Harquahala Complex and the lines and plants
# decided around it. Named here so the subset is a stated choice, not something selected after seeing the answer.
WEST_VALLEY = {"201", "209", "211", "221", "231", "241", "247", "248"}


def weeks(filed: str, decided: str) -> float:
    a = date.fromisoformat(filed[:10])
    b = date.fromisoformat(decided[:10])
    return (b - a).days / 7.0


def measure(cases):
    rows, skipped = [], []
    for c in cases:
        decisions = c.get("decisions") or []
        filed = c.get("filed_date")
        if not decisions or not filed:
            skipped.append((c.get("case"), "no decision record" if not decisions else "no filing date"))
            continue
        first = min(d["decision_date"] for d in decisions)
        span = weeks(filed, first)
        rows.append({
            "case": c.get("case"),
            "docket_number": c.get("docket_number"),
            "company": c.get("company"),
            "project": c.get("project"),
            "filed": filed[:10],
            "first_decision": first,
            "decision_number": next(d["decision_number"] for d in decisions
                                    if d["decision_date"] == first),
            "weeks_filing_to_decision": round(span, 1),
            "decisions_total": len(decisions),
            "status": c.get("status"),
            "west_valley": c.get("case") in WEST_VALLEY,
        })
    negative = [r for r in rows if r["weeks_filing_to_decision"] < 0]
    return rows, skipped, negative


def stats(rows):
    values = sorted(r["weeks_filing_to_decision"] for r in rows)
    q1, q2, q3 = quantiles(values, n=4)
    return {"cases": len(values), "min": values[0], "median": round(median(values), 1), "mean": round(mean(values), 1),
            "max": values[-1], "first_quartile": round(q1, 1), "third_quartile": round(q3, 1)}


def main():
    cases = json.loads(SRC.read_text())["cases"]
    rows, skipped, negative = measure(cases)
    decided = sum(1 for c in cases if c.get("decisions"))
    field = stats(rows)
    subset = stats([r for r in rows if r["west_valley"]])

    OUT.write_text(json.dumps({
        "source": {"file": "acc_dockets.json",
                   "system": "Arizona Corporation Commission eDocket API",
                   "dockets_in_sample": len(cases), "with_decision_records": decided},
        "note": "Elapsed time is the docket's own filed_date to the earliest decision_date it carries. "
                "Amendments and later decisions are counted in decisions_total but not in the span. "
                "The West Valley subset is named in decision_timing.py before the numbers are computed.",
        "field": field,
        "west_valley_subset": subset,
        "excluded_no_decision": [c for c, _ in skipped],
        "negative_spans": [r["case"] for r in negative],
        "cases": sorted(rows, key=lambda r: r["weeks_filing_to_decision"]),
    }, indent=2) + "\n")

    print(f"decided dockets with both dates: {len(rows)} of {len(cases)} in the sample")
    print(f"excluded (no decision record or no filing date): {len(skipped)}")
    print(f"negative spans: {len(negative)}")
    print(f"field: median {field['median']} weeks, quartiles {field['first_quartile']}–{field['third_quartile']}, "
          f"range {field['min']}–{field['max']}")
    print(f"west valley subset: median {subset['median']} weeks across {subset['cases']} cases")

    # Two-sided self-test. Known-true: Case 248 is the project's own permit and its dates are public — filed
    # 2025-08-15, decided 2025-11-21, 98 days, 14.0 weeks. Known-false: a docket without a decision must not be
    # counted, and an undocketed row must not silently become a zero.
    case248 = next(r for r in rows if r["case"] == "248")
    assert (case248["filed"], case248["first_decision"]) == ("2025-08-15", "2025-11-21"), case248
    assert case248["weeks_filing_to_decision"] == 14.0, case248["weeks_filing_to_decision"]
    assert all(c not in [r["case"] for r in rows] for c, _ in skipped), "an undecided docket was measured"
    assert len(rows) < len(cases), "nothing was excluded — the filter is not working"
    assert not negative, f"a decision predates its own application: {negative}"
    print("self-test ok")


if __name__ == "__main__":
    main()
