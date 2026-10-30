"""Read the county's own Board hearing agenda and pull out its land-use calendar.

Maricopa County publishes its Board of Supervisors Planning & Zoning agendas as PDFs through the Agenda Center. The
interesting part is not prose, it is the repeated block — Title / Case # / Supervisor District / Applicant and Owner /
Request / Commission Recommendation — so this extracts those blocks into JSON and counts what the calendar is doing.

    python3 consent_cases.py            # re-reads the two agendas kept beside this file

Kept beside the PDFs and their text extractions, with source records giving the URL, retrieval time and sha256. The
self-test at the bottom asserts the counts that `ledger/county-land-use.md` publishes, including one case that must
not be counted as industrial.
"""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).parent

# (agenda text, output, what the file must contain)
AGENDAS = [
    ("mc-bos-2025-12-10-item10030.txt", "dec2025-consent-cases.json",
     {"items": 12, "industrial_or_utility": 8, "with_commission_vote": 12}),
    ("mc-bos-2026-04-08-pz-agenda.txt", "apr2026-consent-cases.json",
     {"items": 5, "industrial_or_utility": 3, "with_commission_vote": 5}),
]

BLOCK = re.compile(r"\nTitle: ")
CASE = re.compile(r"Case #: (\S+)")
DISTRICT = re.compile(r"Supervisor(?:ial|) District:\s*(\d+)")
REQUEST = re.compile(r"Request: (.{0,300})", re.S)
OWNER = re.compile(r"Applicant and Owner: (.{0,320})", re.S)
VOTE = re.compile(r"On (\d{1,2}/\d{1,2}/\d{2}),\s*the Commission voted (\d+\s*[-–]\s*\d+)")

# A request is counted as land-use conversion only when its own text names the destination district. Guessing from
# a project title ("Energy Park") would let a press-release name do the work of the county's wording.
CONVERTS = ("IUPD", "Utilities")


def blocks(text: str):
    return [b.split("\n")[0].strip() and b for b in BLOCK.split(text)[1:]]


def parse(text: str):
    rows = []
    for b in blocks(text):
        take = lambda pat, group=1: (pat.search(b).group(group).strip() if pat.search(b) else "")
        vote = VOTE.search(b)
        rows.append({
            "title": b.split("\n")[0].strip(),
            "case": take(CASE),
            "district": take(DISTRICT),
            "applicant_owner": " ".join(take(OWNER).split()),
            "request": " ".join(take(REQUEST).split()),
            "commission_recommendation": ({"date": vote.group(1), "vote": vote.group(2)}
                                          if vote else None),
            "converts_to_industrial_or_utility": any(k in take(REQUEST) for k in CONVERTS),
        })
    return rows


def main():
    for name, out, expected in AGENDAS:
        src = HERE / name
        rows = parse(src.read_text())
        votes = {}
        for r in rows:
            if r["commission_recommendation"]:
                votes[r["commission_recommendation"]["vote"].replace(" ", "")] = \
                    votes.get(r["commission_recommendation"]["vote"].replace(" ", ""), 0) + 1
        counts = {
            "items": len(rows),
            "industrial_or_utility": sum(r["converts_to_industrial_or_utility"] for r in rows),
            "with_commission_vote": sum(bool(r["commission_recommendation"]) for r in rows),
            "vote_tally": votes,
        }
        meta = json.loads((src.with_suffix(".source.json")).read_text())
        (HERE / out).write_text(json.dumps(
            {"source_file": name,
             "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
             "agenda": meta["title"],
            "agenda_url": meta["source_url"],
            "agenda_retrieved": meta["retrieved"],
            "agenda_sha256_pdf": meta.get("sha256"),   # the source record beside the text holds the PDF hash
             "counts": counts,
             "cases": rows}, indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: {counts} -> {out}")
        for key, want in expected.items():
            assert counts[key] == want, f"{name}: expected {want} for {key}, found {counts[key]}"

    # The known-false side of the check: an event-space special use permit is not a land-use conversion, and a
    # row must not be counted because its title sounds industrial.
    apr = json.loads((HERE / "apr2026-consent-cases.json").read_text())["cases"]
    event_rows = [r for r in apr if "Event Space" in r["title"]]
    assert event_rows and all(not r["converts_to_industrial_or_utility"] for r in event_rows), \
        "an event-venue SUP was counted as an industrial conversion"
    dec = json.loads((HERE / "dec2025-consent-cases.json").read_text())["cases"]
    named_energy = [r for r in dec if "Energy Park" in r["title"]]
    assert all(r["converts_to_industrial_or_utility"] for r in named_energy), \
        "a named energy park did not actually request a Utilities or IUPD designation"
    print("self-test ok")


if __name__ == "__main__":
    main()
