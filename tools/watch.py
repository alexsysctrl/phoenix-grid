"""A watch on the siting dockets: run the Commission query again and report what changed.

`acc_dockets.py` answers "what has been decided, as of today". A single answer is not useful for a forecast — the
thing that matters is *change*: a new decision number, a grant amended, a docket moving out of *Compliance Due*, a
case that was pending and now is not. That is only visible by running the same query on a schedule and diffing it.

This script is the worker for that schedule. A monthly job calls it on the first day
of each month. It runs the query, compares the new ledger with the previous one it kept, and reports the diff in
three directions — decided since last time, newly pending, and status changes — and appends one line to
`siting-watch.log` so a reader can see the watch has actually run.

`--seed` records today's answer as the baseline without re-querying, so the first real comparison happens next month
rather than today.

Run:  python3 watch.py --seed         # baseline from the ledger already on disk
      python3 watch.py                # re-query the Commission and report the diff
      python3 watch.py --self-test
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEDGER = DATA / "acc_dockets.json"
STATE = DATA / "state"
PREV = STATE / "siting-previous.json"
CHANGES = STATE / "siting-changes-latest.json"
LOG = DATA / "siting-watch.log"


def rows_of(ledger: dict) -> dict[str, dict]:
    """Key the ledger by docket number so a comparison is per-docket rather than per-position."""
    return {r["docket_number"]: r for r in ledger["cases"]}


def decide_key(r: dict) -> tuple:
    return tuple(sorted((d["decision_number"], d["decision_date"]) for d in r.get("decisions", [])))


def diff(old: dict, new: dict) -> dict:
    a, b = rows_of(old), rows_of(new)
    out = {"new_dockets": sorted(set(b) - set(a)), "gone_dockets": sorted(set(a) - set(b)),
           "newly_decided": [], "new_decisions": [], "status_changed": [], "unchanged": 0}
    for dn in sorted(set(a) & set(b)):
        ra, rb = a[dn], b[dn]
        da, db = decide_key(ra), decide_key(rb)
        if da != db:
            added = [d for d in rb.get("decisions", []) if (d["decision_number"], d["decision_date"]) not in da]
            entry = {"docket_number": dn, "case": rb.get("case"), "company": rb.get("company"),
                     "added": added, "was_decided": bool(da), "now_decided": bool(db),
                     "status": rb.get("status")}
            out["new_decisions"].append(entry)
            if not da and db:
                out["newly_decided"].append(entry)
        if ra.get("status") != rb.get("status"):
            out["status_changed"].append({"docket_number": dn, "company": rb.get("company"),
                                          "was": ra.get("status"), "now": rb.get("status")})
        if da == db and ra.get("status") == rb.get("status"):
            out["unchanged"] += 1
    return out


def run_query() -> None:
    print("running the Commission docket query ...")
    r = subprocess.run([sys.executable, str(DATA / "acc_dockets.py")], cwd=DATA, capture_output=True, text=True,
                       timeout=900)
    if r.returncode != 0:
        raise SystemExit(f"acc_dockets.py failed (rc={r.returncode}): {r.stderr[-400:]}")


def main(seed: bool) -> int:
    if not LEDGER.exists():
        raise SystemExit(f"{LEDGER} is missing — run acc_dockets.py first")
    if not seed:
        run_query()
    new = json.loads(LEDGER.read_text())
    STATE.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if not PREV.exists():
        PREV.write_text(json.dumps(new))
        line = f"{stamp} seeded baseline: {new['summary']['dockets_queried']} dockets, {new['summary']['with_decisions']} decided"
        LOG.write_text((LOG.read_text() if LOG.exists() else "") + line + "\n")
        print(line)
        return 0
    d = diff(json.loads(PREV.read_text()), new)
    CHANGES.write_text(json.dumps({"ran": stamp, "diff": d}, indent=2))
    PREV.write_text(json.dumps(new))
    n_new = len(d["newly_decided"]) + len(d["new_decisions"])
    line = (f"{stamp} dockets {new['summary']['dockets_queried']} decided {new['summary']['with_decisions']}"
            f" | newly decided: {len(d['newly_decided'])} | new decisions: {n_new}"
            f" | status changes: {len(d['status_changed'])} | new dockets: {len(d['new_dockets'])}"
            f" | unchanged: {d['unchanged']}")
    LOG.write_text((LOG.read_text() if LOG.exists() else "") + line + "\n")
    print(line)
    for e in d["new_decisions"]:
        for a in e["added"]:
            print(f"  NEW: {e['docket_number']} ({e['company']}) -> Decision {a['decision_number']} {a['decision_date']}")
    for s in d["status_changed"]:
        print(f"  STATUS: {s['docket_number']} ({s['company']}) {s['was']} -> {s['now']}")
    return 0


def self_test() -> int:
    """A change-reporter that reports nothing is worthless, and one that reports everything is worse. Both cases."""
    base = {"cases": [
        {"docket_number": "L-1", "case": "1", "company": "A", "status": "Open Meeting Pending", "decisions": []},
        {"docket_number": "L-2", "case": "2", "company": "B", "status": "Compliance Due",
         "decisions": [{"decision_number": 100, "decision_date": "2025-01-01"}]},
    ]}
    moved = json.loads(json.dumps(base))
    moved["cases"][0]["status"] = "Compliance Due"
    moved["cases"][0]["decisions"] = [{"decision_number": 200, "decision_date": "2026-02-02"}]
    d = diff(base, moved)
    fails = []
    if len(d["newly_decided"]) != 1 or d["newly_decided"][0]["docket_number"] != "L-1":
        fails.append("a case decided since last time was not reported as newly decided")
    if len(d["status_changed"]) != 1 or d["status_changed"][0]["now"] != "Compliance Due":
        fails.append("a status change was not reported")
    if d["unchanged"] != 1:
        fails.append(f"the untouched docket was not counted as unchanged (got {d['unchanged']})")
    same = diff(base, json.loads(json.dumps(base)))
    if any([same["new_decisions"], same["newly_decided"], same["status_changed"], same["new_dockets"],
            same["gone_dockets"]]):
        fails.append("identical ledgers produced changes — the diff is not quiet when nothing moved")
    if same["unchanged"] != 2:
        fails.append("the quiet case must count every docket as unchanged")
    print("siting-watch self-test:", "FAIL " + "; ".join(fails) if fails else
          "PASS (a new decision and a status change are reported; an unchanged ledger reports nothing)")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main(seed="--seed" in sys.argv))
