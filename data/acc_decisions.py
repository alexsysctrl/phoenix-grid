#!/usr/bin/env python3
"""Fetch the text of ACC decisions, by decision number.

Found while reading one decision (2026-10-28): the Commission's document host serves every filed document as
`https://docket.images.azcc.gov/{barCode}.pdf`, and the bar code is reachable from the decision number through the
eDocket API. That turns my outcomes ledger — 67 decision numbers — into a corpus: not just "granted on this date"
but what was actually granted, with its conditions.

Two facts about the host, both measured today: its TLS certificate is issued for `CN=corporations.images.azcc.gov`
and expired 27 October 2026, so verification is disabled here rather than the fetch being skipped; and the PDFs are
scans with an OCR text layer, so `pypdf` extraction returns readable but imperfect text — the original page line
numbers come through, and digits are unreliable (`ten (10) years` extracts as `ten (IO) years`). Quote the PDF, not the
extraction, in anything a person reads.

Usage: python3 acc_decisions.py            # the West Valley certificates in acc_dockets.json
       python3 acc_decisions.py 81564 …   # explicit decision numbers
"""
import json
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://efiling.azcc.gov/api/edocket/"
IMAGES = "https://docket.images.azcc.gov"
HERE = Path(__file__).resolve().parent
OUT = HERE / "decisions"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# Unverified because the state's document host has an expired certificate (see module docstring).
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def api_post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def documents_for_decision(decision_number: int) -> list[dict]:
    """Filed documents attached to a decision number.

    The row field is `imageNumber`, not `barCode`: in the search response `barCode` is null while `imageNumber`
    carries the number the image host serves the PDF from. Confirmed against Decision 81564 → imageNumber
    0000215662 → the 18-page decision.
    """
    out = api_post("documentSearchRequest",
                   {"decisionNumber": decision_number, "searchAsString": True,
                    "currentPageIndex": 0, "rowsPerPage": 50, "rowsToSkip": 0})
    rows = out.get("searchResult") or []
    return [d for d in rows if d.get("imageNumber") or d.get("barCode")]


def file_number(doc: dict) -> str:
    return str(doc.get("imageNumber") or doc.get("barCode"))


def decision_document(docs: list[dict], decision_number: int) -> dict | None:
    """The decision's own filing: `filedBy` names the decision number, or the description says what was decided."""
    named = [d for d in docs if f"(#{decision_number})" in str(d.get("filedBy") or "")]
    if named:
        return named[0]
    kinds = [d for d in docs if str(d.get("description") or "").startswith("Decision")]
    return kinds[0] if kinds else None


def download_pdf(bar_code: str) -> bytes | None:
    url = f"{IMAGES}/{bar_code}.pdf"
    try:
        with urllib.request.urlopen(url, timeout=90, context=CTX) as r:
            return r.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"    {bar_code}: no file ({e})")
        return None


def pdf_text(blob: bytes) -> tuple[str, int]:
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(blob))
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n\n".join(f"=== PAGE {i + 1} ===\n{t}" for i, t in enumerate(pages)), len(pages)


def targets_from_ledger() -> list[int]:
    """Decisions on dockets that name West Valley places and are certificates of environmental compatibility."""
    ledger = json.load(open(HERE / "acc_dockets.json"))
    wanted = []
    for case in ledger["cases"]:
        places = case.get("west_valley_places_named") or []
        if not places:
            continue
        for d in case.get("decisions") or []:
            kind = str(d.get("decision_type") or "")
            if "Decision" not in kind:
                continue
            wanted.append(int(d["decision_number"]))
    return sorted(set(wanted))


def fetch(decision_number: int) -> dict:
    docs = documents_for_decision(decision_number)
    doc = decision_document(docs, decision_number)
    record = {"decision_number": decision_number, "documents_seen": len(docs)}
    if doc is None:
        record["error"] = "no filing with an image number attached to this decision"
        return record
    record.update({"file_number": file_number(doc), "document_id": doc.get("documentID"),
                   "filed_by": doc.get("filedBy"), "description": doc.get("description"),
                   "filed_date": doc.get("filedDate")})
    blob = download_pdf(file_number(doc))
    if blob is None:
        record["error"] = "pdf not fetched"
        return record
    OUT.mkdir(exist_ok=True)
    pdf_path = OUT / f"{decision_number}-{file_number(doc)}.pdf"
    pdf_path.write_bytes(blob)
    text, pages = pdf_text(blob)
    (OUT / f"{decision_number}.txt").write_text(text)
    record.update({"pdf": str(pdf_path), "pages": pages, "chars": len(text),
                   "bytes": len(blob)})
    return record


def self_test() -> None:
    """A known-true case and a known-false one, both against the files this tool actually produced.

    Numbers in this OCR layer are unreliable: the scanned `ten (10) years` extracts as `ten (IO) years`, so a test
    that asserts a digit string fails on a document that is present and correct. The assertions use the words around
    the numbers. Any numeric claim in something a person reads is quoted from the PDF page, not from this text layer.
    """
    text = (OUT / "81564.txt").read_text()
    for phrase in ["CERTIFICATE OF", "expire ten", "right-of-way", "Arizona State Museum",
                   "Native Plant Law", "acres", "granted upon the following conditions"]:
        assert phrase.upper() in text.upper(), f"81564 text is missing {phrase!r}"
    for absent in ["denied", "certificate denied", "application withdrawn", "certificate revoked"]:
        assert absent not in text.lower(), f"81564 unexpectedly contains {absent!r}"
    pages = text.count("=== PAGE ")
    assert pages >= 15, f"expected an 18-page decision, got {pages} pages"
    with_cond = sum(1 for f in OUT.glob("*.txt")
                    if "granted upon the following conditions" in f.read_text().lower())
    assert with_cond >= 40, f"only {with_cond} fetched decisions carry a conditions section"
    print(f"self-test: 7 known-true phrases and 4 known-absent ones as expected, {pages} pages extracted, "
          f"{with_cond} decision texts contain a conditions section")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test()
        return 0
    numbers = [int(a) for a in sys.argv[1:] if re.fullmatch(r"\d+", a)]
    scope = "given on the command line"
    if not numbers:
        numbers, scope = targets_from_ledger(), "West-Valley-naming dockets in the outcomes ledger"
    print(f"{len(numbers)} decisions in scope ({scope})")
    OUT.mkdir(exist_ok=True)
    results = []
    for n in numbers:
        print(f"  {n}: ", end="", flush=True)
        try:
            r = fetch(n)
        except Exception as e:
            r = {"decision_number": n, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        print(f"{(r.get('description') or r.get('error', ''))[:48]} · file {r.get('file_number')} · "
              f"{r.get('pages', 0)} pages · {r.get('chars', 0)} chars")
    (OUT / "index.json").write_text(json.dumps(results, indent=2))
    got = sum(1 for r in results if r.get("pages"))
    print(f"done: {got}/{len(results)} decision texts stored under {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
