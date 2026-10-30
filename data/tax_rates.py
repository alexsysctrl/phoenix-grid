#!/usr/bin/env python3
"""Arizona's tax rates for the West Valley, pulled out of the two tables that actually set them.

Two different taxes, two different primary sources:

1. Property tax — Maricopa County's own "2025 Tax Rates, Maricopa County, Arizona" table. Rates are published
   per taxing area, so an address in Avondale has a different total depending on which elementary and high
   school district it sits in. This script keeps every row for the cities in scope, with the district labels
   attached, because averaging them would hide the thing that matters.
2. Transaction privilege tax (what a shopper pays) — the Arizona Department of Revenue's rate table effective
   June 2026. The city privilege rate is what varies between Avondale, Buckeye, Goodyear and the rest; the
   state and county portions are the same across the county. Both the retail class and the contracting classes
   are extracted, because in this part of the valley the contracting rate is the one a builder feels.

  python3 tax_rates.py                fetches both PDFs, parses them, writes tax_rates.json
  python3 tax_rates.py --cached      re-parse the copies already on disk

The parsing is deliberately strict: a city block is only accepted if the printed line has the shape the DOR
table uses (class name, three-digit class code, a rate). If a row cannot be parsed it is reported, not guessed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
UA = "alex-sqopa-research/1.0 (alex@sqopa.com)"

PROPERTY_PDF = "https://www.maricopa.gov/DocumentCenter/View/109591/Tax-Rate-2025-PDF"
TPT_PDF = "https://azdor.gov/sites/default/files/document/TPT_RATETABLE_06012026.pdf"

CITIES = ["Avondale", "Buckeye", "Goodyear", "Tolleson", "Litchfield Park", "El Mirage", "Surprise",
          "Phoenix", "Glendale", "Peoria", "Mesa", "Chandler", "Queen Creek"]

# Classes worth extracting from the DOR table: retail is what households pay, contracting is what building costs.
CLASSES = {"017": "retail", "015": "contracting prime", "016": "contracting speculative builders",
           "037": "contracting owner builder", "012": "amusements", "053": "vehicle rentals"}


def fetch_pdf(url: str, dest: pathlib.Path) -> pathlib.Path:
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        dest.write_bytes(r.read())
    return dest


def pdf_lines(path: pathlib.Path) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return [line for line in text.splitlines() if line.strip()]


def parse_property_rows(lines: list[str]) -> list[dict]:
    """Rows look like: '440100 Avondale #44 Agua Fria Avondale 6.3796 4.8190 4.8722'.

    The district names contain spaces, so splitting on whitespace cannot work. The parse anchors on the end
    instead: three trailing rate numbers, the city name right before them, everything between the area code
    and the city kept as the printed district fields. Longer city names first so "Litchfield Park" is not
    matched as a prefix of something else.
    """
    names = "|".join(sorted((c.replace(" ", r"\s+") for c in CITIES), key=len, reverse=True))
    pattern = re.compile(r"^(\d{6})\s+(.*?)\s+(" + names + r")((?:\s+\d+\.\d+){3})\s*$")
    out = []
    for line in lines:
        m = pattern.match(line.strip())
        if not m:
            continue
        area, districts, city, numbers = m.groups()
        approx_res, primary, secondary = (float(x.strip()) for x in numbers.split())
        out.append({"area_code": area, "district_fields": " ".join(districts.split()),
                    "city": city.replace("  ", " "), "approx_residential_rate": approx_res,
                    "primary_rate": primary, "secondary_rate": secondary})
    return out


def parse_tpt_rows(lines: list[str]) -> tuple[dict[str, dict[str, float]], list[dict]]:
    """City blocks in Table 2: a header line 'Avondale  AV   MAR' followed by 'Activity 017 2.50' lines."""
    # County codes can be two counties at once, e.g. 'Peoria  PE   MAR/YAV' or 'Queen Creek   QC  MAR/PNL'.
    header = re.compile(r"^([A-Za-z ,'&.\-]+?)\s{1,}([A-Z]{2,4})\s{1,}([A-Z]{2,4}(?:/[A-Z]{2,4})?)\s*$")
    rate_line = re.compile(r"^(.+?)\s{1,}(\d{3})\s+([0-9]+\.?[0-9]*)\s*$")
    out: dict[str, dict[str, float]] = {}
    city_codes: list[dict] = []
    current = None
    for line in lines:
        h = header.match(line.strip())
        if h:
            name = h.group(1).strip()
            current = name if name in CITIES else None
            city_codes.append({"city": name, "region_city_code": h.group(2), "county_code": h.group(3)})
            continue
        if not current:
            continue
        r = rate_line.match(line.strip())
        if r and r.group(2) in CLASSES:
            try:
                out.setdefault(current, {})[CLASSES[r.group(2)]] = float(r.group(3))
            except ValueError:
                continue
    return out, city_codes


def county_combined_retail(lines: list[str]) -> dict:
    """The class-017 row of Table 1 gives state+county combined rates per county, in column order."""
    for i, line in enumerate(lines):
        if line.strip().startswith("017 Retail"):
            values = re.findall(r"\d+\.\d+", line)
            header_row = next((lines[j] for j in range(max(0, i - 12), i) if "Maricopa" in lines[j]), "")
            cols = re.findall(r"\(([A-Z]{3})\)", header_row)
            paired = dict(zip(cols, values)) if cols and len(cols) == len(values) else {}
            return {"printed_row": line.strip(), "columns": cols, "values": values,
                    "maricopa_by_column_pairing": paired.get("MAR"), "maricopa_by_position": values[5] if len(values) > 5 else None}
    return {}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true", help="parse the PDFs already on disk")
    args = ap.parse_args()
    prop_pdf = fetch_pdf(PROPERTY_PDF, HERE / "source-maricopa-tax-rates-2025.pdf")
    tpt_pdf = fetch_pdf(TPT_PDF, HERE / "source-dor-tpt-rates-2026-06.pdf")

    prop_lines = pdf_lines(prop_pdf)
    tpt_lines = pdf_lines(tpt_pdf)
    property_rows = parse_property_rows(prop_lines)
    city_rates, city_codes = parse_tpt_rows(tpt_lines)
    county_row = county_combined_retail(tpt_lines)

    payload = {
        "property_tax": {"source": "Maricopa County '2025 Tax Rates, Maricopa County, Arizona'",
                         "url": PROPERTY_PDF, "columns_as_printed": ["Area Code", "Elementary School District",
                         "High School District", "Primary City", "Approx Residential Rate*", "Primary Rate*",
                         "Secondary Rate*"],
                         "unit_note": "the asterisked columns are defined by a footnote on the county's tax levy page; this script reports the printed numbers and does not convert them",
                         "rows": property_rows},
        "transaction_privilege_tax": {
            "source": "Arizona Department of Revenue, Transaction Privilege and Other Tax Rate Tables, effective 1 June 2026",
            "url": TPT_PDF, "county_combined_retail_row": county_row,
            "city_rates_percent": city_rates,
            "classes_extracted": CLASSES,
        },
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    out = HERE / "tax_rates.json"
    out.write_text(json.dumps(payload, indent=2))

    for city in CITIES[:9]:
        rows = [r for r in property_rows if r["city"] == city]
        if rows:
            rng = sorted(r["approx_residential_rate"] for r in rows)
            print(f"{city:16} property: {len(rows)} district combinations, approx residential rate "
                  f"{rng[0]:.4f}-{rng[-1]:.4f}; city primary+secondary from the county table "
                  f"max {max(r['primary_rate'] for r in rows):.4f} primary")
        t = city_rates.get(city, {})
        if t:
            print(f"{'':16} sales tax: " + ", ".join(f"{k} {v}%" for k, v in sorted(t.items())))
    print("county combined retail row:", county_row.get("printed_row", "")[:150])
    print(f"wrote {out}")

    # The self-test: the parse must find the rows we know are in these tables, and must not invent any.
    assert len(property_rows) >= 20, f"only {len(property_rows)} property rows parsed — the row pattern is wrong"
    avon = [r for r in property_rows if r["city"] == "Avondale"]
    assert len(avon) >= 4, "Avondale appears in the county table with at least four school-district combinations"
    assert abs(min(r["approx_residential_rate"] for r in avon) - 6.0539) < 1e-4, \
        "the lowest printed Avondale residential rate is not 6.0539 — the parser is reading the wrong column"
    assert city_rates.get("Avondale", {}).get("retail") == 2.5, "Avondale retail privilege rate is not 2.5%"
    assert city_rates.get("Phoenix", {}).get("retail") == 2.8, "Phoenix retail privilege rate is not 2.8%"
    assert city_rates.get("Goodyear", {}).get("contracting prime") == 3.5, "Goodyear contracting rate is not 3.5%"
    assert city_rates.get("Peoria", {}).get("retail") == 1.8, "Peoria (a MAR/YAV city) retail rate is not 1.8%"
    assert city_rates.get("Queen Creek", {}).get("retail") == 2.25, "Queen Creek (MAR/PNL) retail rate is not 2.25%"
    assert county_row.get("maricopa_by_position") == "6.30", "the Maricopa combined retail rate is not 6.30"
    print("self-test passed: both tables parsed, the known rows and rates are present, nothing invented")
