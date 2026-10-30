"""Harquahala North: the applicant's own account of why a 500 kV line is needed west of Phoenix.

LS Case No. 248, docket L-21304A-25-0169-00248 — an application by Harquahala Complex HoldCo LLC for a Certificate
of Environmental Compatibility authorising "the 500-KV Harquahala North Transmission Line Project and associated
switchyards, located in Harquahala Valley, in west Maricopa County, Arizona." The evidentiary hearing was held
*in Avondale* on 29 September 2025, which is why this document matters to this project: a west-Maricopa
transmission case was heard in the town whose property market is being studied here, and the transcript of that
hearing is public.

The value of a siting transcript is different from the value of a utility's annual report. The annual report
describes a programme. A transcript is the applicant, on the record, under questioning by the committee, saying in
plain language what it believes the constraint is and what it has already built. The single most useful sentence in
Volume I is the applicant's own explanation of why this corridor: coordinating with APS, "the challenges in getting
more power into the Phoenix metro", and the siting logic — build generation where the import capability is, then
put the load next to it.

Two limits recorded up front. Volume I is the evidentiary hearing only: 175 pages, opening statement, virtual tour,
public comment, closing statement, deliberations — the Committee's vote is at page 377, in Volume II, which is not
here, so nothing in this file states the outcome of the application. And a PDF of a court transcript interleaves
the transcript's own line numbers into the sentences ("with over 1,000 13 megawatts"), so matching and quoting have
to be done on text with those markers removed. `clean` does that, and the cleaning is asserted on a sample rather
than trusted: one- and two-digit numbers inside a sentence are removed along with the markers, which is a known
cost of the method, and it is why the megawatt figures quoted here are the four-digit ones.

Run:  python3 harquahala_transcript.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pypdf

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source-ls248-harquahala-transcript-vol1.pdf"

WS = re.compile(r"\s+")
# Transcript line numbers are printed 1–25 in the left column; the marker for a line's start in the extracted text
# is a bare one- or two-digit token, or a bare ')'. Anything with three or more digits is a real number.
MARKER = re.compile(r"(?<=\s)\d{1,2}(?=\s)|(?<=\s)\)(?=\s)")

FOLD = {ord(k): v for k, v in {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
                               "\u00a0": " ", "\u2013": "-", "\u2014": "-"}.items()}


def fold(text: str) -> str:
    return text.translate(FOLD)


def clean(text: str) -> str:
    """Collapse whitespace and drop the transcript's line-number and column-marker tokens."""
    return WS.sub(" ", MARKER.sub(" ", text)).strip()


def pages_of(path: Path) -> list[str]:
    return [p.extract_text() or "" for p in pypdf.PdfReader(str(path)).pages]


def locate(pages: list[str], phrase: str) -> tuple[int, str]:
    """Find `phrase` in the cleaned transcript and return (1-based page, the cleaned text as it appears)."""
    target = fold(clean(phrase)).lower()
    assert target and not target.startswith(" ") and not target.endswith(" ")
    for i, raw in enumerate(pages):
        joined = fold(clean(raw)).lower()
        at = joined.find(target)
        if at < 0:
            continue
        return i + 1, clean(raw)[at: at + len(target)]
    raise LookupError(f"not in Volume I of the filed transcript: {phrase!r}")


CLAIMS = [
    {
        "claim": "Where and when it was heard",
        "quote": "At: Avondale, Arizona",
        "note": "Page 1 of the transcript. The same block gives 'Date: September 29, 2025' and the filing date of the transcript.",
        "use": "A west-Maricopa transmission case heard in Avondale — the place this project's property data is about.",
    },
    {
        "claim": "The applicant's stated reason for the line",
        "quote": "one thing that we have identified in coordinating with APS is really the challenges in getting more power into the Phoenix metro",
        "note": "Garret Bean, on the applicant's side, describing the Harquahala complex and its relation to APS.",
        "use": "The constraint, in the applicant's words rather than a utility's or a journalist's: bringing power *into* the metro is the hard part.",
    },
    {
        "claim": "The siting logic, stated plainly",
        "quote": "this project sits at a location kind of west of the Phoenix metro that is a major intertie",
        "note": "Continued in the same answer: 'for load growth that really helps APS kind of balance where they have future load growth by co-locating it next to the generation.'",
        "use": "Why generation and data centres are being placed in the west valley rather than near the load: the import capability is what the site offers.",
    },
    {
        "claim": "What is already built and contracted at Harquahala",
        "quote": "Copia has built 450 megawatts of operational facilities in the Harquahala Valley, with over 1,000 megawatts total that are contracted and in construction",
        "note": "Garret Bean, on the applicant's other projects. Elsewhere the transcript records his team's portfolio as 'over 30 gigawatts of generation assets' and '10 gigawatts of data center campuses across the U.S.' — both in passages this file does not quote.",
        "use": "Scale, on the record, from the developer: several hundred megawatts operating and more than a gigawatt contracted at one site west of the metro.",
    },
    {
        "claim": "Data centres are the load",
        "quote": "The other project that we are working on in the region is a data center project",
        "note": "Bean, describing what else the applicant is doing in the Harquahala Valley.",
        "use": "Confirms the load type behind the transmission request, from the party making the request.",
    },
    {
        "claim": "Water purchases by the towns in this corridor",
        "quote": "with large purchases from municipalities like Queen Creek and Buckeye",
        "note": "The Committee's chair asking about 'the water project' the applicant is also involved in; the witness confirms and says he is not a representative of that project.",
        "use": "Municipal water purchases by growing towns in the same corridor, named on the record at a transmission hearing.",
    },
    {
        "claim": "Right-of-way is the work",
        "quote": "it requires different right-of-ways, working with Maricopa Department of Transportation, and also obtaining several entitlements for the ancillary or other projects",
        "note": "Bean, on milestones achieved, adding that entitlements are being obtained for the ancillary projects.",
        "use": "The actual gating item for a transmission corridor in this area: roadway crossings and county entitlements.",
    },
    {
        "claim": "Public notice, as the applicant described it",
        "quote": "the CEC application was sent to two Buckeye public libraries, the downtown branch as well as the Coyote branch",
        "note": "From the applicant's notice programme: two Buckeye branches, a project website with remote participation links, signs, and paid social advertising.",
        "use": "How a siting case reaches the towns it crosses — and a way to find the notice for any future case in this corridor.",
    },
]

# Volume II contains the decision. Asserting their absence proves this file is only what it says it is.
NOT_IN_VOLUME_I = ["voted to approve", "Recommended Decision", "the Certificate is granted"]


def build(pages: list[str]) -> dict:
    rows = []
    for c in CLAIMS:
        page, raw = locate(pages, c["quote"])
        rows.append({**c, "page": page, "verbatim": raw})
    return {
        "source": {
            "title": "Arizona Power Plant and Transmission Line Siting Committee, LS Case No. 248, transcript of proceedings, Volume I",
            "docket": "L-21304A-25-0169-00248",
            "applicant": "Harquahala Complex HoldCo, LLC",
            "hearing": "Avondale, Arizona, 29 September 2025",
            "pages_in_pdf": len(pages),
            "kept_as": SOURCE.name,
            "cleaning": "whitespace collapsed and transcript line-number/column markers removed before matching; "
                        "three-digit numbers are left alone, so the figures quoted here are four-digit ones",
        },
        "claims": rows,
        "volume_ii_holds": "the Committee's vote (index: Deliberations at page 259, Vote at page 377)",
    }


def selftest() -> None:
    # the cleaning is the mechanism this file depends on, so it is asserted on a constructed case
    assert clean("with over 1,000 13 megawatts total") == "with over 1,000 megawatts total", \
        f"line markers were not removed: {clean('with over 1,000 13 megawatts total')!r}"
    assert clean("450 megawatts of operational facilities") == "450 megawatts of operational facilities", \
        "a three-digit figure must survive the cleaning"
    # known-false side of that rule, stated rather than discovered later
    assert clean("over 25 utility-scale projects") == "over utility-scale projects", \
        "the documented cost of the method changed without notice"
    # and the other side of that rule: numbers joined by punctuation are not markers
    assert clean("A.R.S. 40-360 et seq. in 20-25 days") == "A.R.S. 40-360 et seq. in 20-25 days", \
        "a statute citation or a hyphenated range must survive the cleaning"
    pages = pages_of(SOURCE)
    page, verbatim = locate(pages, "At: Avondale, Arizona")
    assert page == 1, f"the hearing location is on the first page of the transcript, found page {page}"
    assert "Avondale" in verbatim
    out = build(pages)
    assert len(out["claims"]) == len(CLAIMS), "a claim dropped out"
    assert all(c["page"] >= 1 for c in out["claims"])
    assert any(c["page"] > 1 for c in out["claims"]), "every claim on page 1 means the extractor is matching the caption only"
    # known-true: the index of this volume itself points the vote outside this volume, which is the source of the limit
    page, _ = locate(pages, "Deliberations")
    assert page == 2, f"the index of proceedings is on page 2 of the transcript, found page {page}"
    assert "377" in clean(pages[1]), "the index should list the vote at page 377, outside Volume I"
    # known-false: the decision is in Volume II and must not be findable here
    for phrase in NOT_IN_VOLUME_I:
        try:
            locate(pages, phrase)
        except LookupError:
            continue
        raise AssertionError(f"a Volume II item appears in Volume I: {phrase!r}")
    # a phrase that cannot be in a 2025 Arizona transcript
    try:
        locate(pages, "the line was completed in 2019")
        raise AssertionError("the locator accepted something that cannot be in this document")
    except LookupError:
        pass
    print(f"self-test passed: {len(CLAIMS)} claims located in a {len(pages)}-page transcript with pages, the "
          "cleaning rule asserted on both sides, and the Volume II decision confirmed absent from Volume I")


if __name__ == "__main__":
    selftest()
    out = build(pages_of(SOURCE))
    (HERE / "harquahala_transcript.json").write_text(json.dumps(out, indent=2))
    print(f"source: {out['source']['title']}")
    print(f"pages {out['source']['pages_in_pdf']}, kept as {out['source']['kept_as']}; {out['volume_ii_holds']}")
    for c in out["claims"]:
        print(f"  p{c['page']:>4}  {c['claim']}")
        print(f"        \"{c['verbatim'][:160]}\"")
