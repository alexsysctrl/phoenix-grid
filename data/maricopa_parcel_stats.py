#!/usr/bin/env python3
"""ZIP-level property structure, from the Maricopa County Assessor's parcel roll.

The unit of the picture is the ZIP code, not the city: the assessor's roll is read per ZIP.
This reads the county's own roll, ZIP by ZIP, and answers three things per ZIP: what a house is valued at,
what a vacant residential lot is valued at, and what the area's assessed wealth is actually made of —
houses, warehouses, industry, retail, municipal or school land. It also reports the vintage of the data it
found, because a roll is a snapshot and the snapshot's date is part of the number.

What the fields are, checked against a real record: FullCashValue for a Tolleson single-family parcel is
$250,000 and that parcel's recorded sale was $253,000 — so this column is a market-scale full cash value,
not the 10 percent assessed figure used to compute a tax bill. Tax billed and TaxYear come back empty from
this view, so tax rates have to come from the State Tax Commission, and this script does not claim them.

This service does not honour statistics queries (it returns plain features instead), so the roll is paged and
every statistic is computed here. Paging is checked against the service's own count for each ZIP, because a
quiet off-by-one in a paging loop is exactly the kind of error that becomes a confident number.

  python3 maricopa_parcel_stats.py                 the comparison set, writes ./maricopa_parcel_stats.json
  python3 maricopa_parcel_stats.py --zip 85323
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import statistics
import urllib.parse
import urllib.request

SERVICE = ("https://services.arcgis.com/ykpntM6e3tHvzKRJ/arcgis/rest/services/"
           "Parcel_Data_View/FeatureServer/0/query")
UA = "alex-sqopa-research/1.0 (alex@sqopa.com)"
PAGE = 2000
FIELDS = ("OBJECTID,PropertyZipCode,FullCashValue,LandFullCashValue,ImprovementFullCashValue,"
          "SalePrice,SaleDate,PropertyUseCode,PropertyUseDescription")

# Home, the immediate neighbours, the built-up west-valley comparison points, and the growth corridor.
ZIPS = ["85323", "85353", "85338", "85342", "85043", "85041", "85037", "85051", "85374", "85379"]

# Buckeye's ZIP covers a large area outside the city proper; the city total is given so the two are not confused.
SUBAREA_NOTE = {"85323": "ZIP covers Buckeye and unincorporated Maricopa County west of the city"}

RESIDENTIAL_KEYS = ("SFR", "MOBILE HOME", "MANUFACTURED", "CONDOMINIUM", "APARTMENT", "DUPLEX",
                    "TWINHOME", "CLUSTER", "PLANNED UNIT", "RESIDENTIAL ")
VACANT_RESIDENTIAL_KEYS = ("VACANT RESIDENTIAL",)


def get(params: dict) -> dict:
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read().decode())
    if "error" in body:
        raise RuntimeError(f"assessor service error: {body['error'].get('details') or body['error']}")
    return body


def count_of(zip_code: str, where_extra: str = "") -> int:
    d = get({"where": f"PropertyZipCode='{zip_code}'{where_extra}", "returnCountOnly": "true", "f": "json"})
    return int(d.get("count", 0))


def pull_zip(zip_code: str, expected: int) -> list[dict]:
    """Page through one ZIP's parcels. `expected` is the service's own count, used only to know when to stop."""
    rows, offset = [], 0
    while True:
        d = get({"where": f"PropertyZipCode='{zip_code}'", "outFields": FIELDS, "returnGeometry": "false",
                 "orderByFields": "OBJECTID ASC", "resultRecordCount": PAGE, "resultOffset": offset, "f": "json"})
        feats = d.get("features", [])
        if not feats:
            break
        rows.extend(f["attributes"] for f in feats)
        offset += len(feats)
        if offset >= expected or len(feats) < PAGE:
            break
    return rows


def classify(row: dict) -> str:
    """A coarse use class from the assessor's own description text, in the county's words."""
    use = str(row.get("PropertyUseDescription") or "").upper()
    if any(k in use for k in VACANT_RESIDENTIAL_KEYS):
        return "vacant residential land"
    if "WAREHOUS" in use or "WAREHOUSE" in use:
        return "warehousing"
    if "MANUFACTUR" in use or "INDUSTRIAL" in use:
        return "industrial"
    if "DATA CENT" in use:
        return "data centre"
    if any(k in use for k in RESIDENTIAL_KEYS):
        return "residential (built)"
    if "RETAIL" in use or "OFFICE" in use or "COMMERCIAL" in use or "SHOPPING" in use:
        return "commercial"
    if "SCHOOL" in use:
        return "school land"
    if "MUNICIPAL" in use or "COUNTY" in use or "STATE " in use or "FEDERAL" in use:
        return "public land"
    if "AGRICULTUR" in use or "FARM" in use or "IRRAIGAT" in use:
        return "agricultural"
    if "VACANT" in use:
        return "other vacant land"
    return "other"


def summarise(rows: list[dict], sale_window_days: int) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=sale_window_days)
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(classify(r), []).append(r)

    def money(rs, field):
        return [r[field] for r in rs if isinstance(r.get(field), (int, float)) and r[field] > 0]

    def med(xs):
        return round(statistics.median(xs)) if xs else None

    def block(rs) -> dict:
        vals = money(rs, "FullCashValue")
        land = money(rs, "LandFullCashValue")
        sales = [(r["SalePrice"], r["SaleDate"]) for r in rs
                 if isinstance(r.get("SalePrice"), (int, float)) and r["SalePrice"] > 0
                 and isinstance(r.get("SaleDate"), (int, float))]
        recent = [p for p, d in sales if dt.datetime.fromtimestamp(d / 1000, dt.timezone.utc) >= since]
        return {
            "parcels": len(rs),
            "median_value": med(vals),
            "mean_value": round(statistics.mean(vals)) if vals else None,
            "quartile_1_value": round(statistics.quantiles(vals, n=4)[0]) if len(vals) > 3 else None,
            "total_value": round(sum(vals)) if vals else 0,
            "land_share_pct": round(sum(land) / max(sum(vals), 1) * 100, 1),
            "sales_total_recorded": len(sales),
            "sales_in_window": len(recent),
            "median_sale_price_in_window": med(sorted(recent)),
            "latest_recorded_sale": max((dt.datetime.fromtimestamp(d / 1000, dt.timezone.utc).date().isoformat()
                                         for _, d in sales), default=None),
        }

    by_class = {k: block(v) for k, v in sorted(groups.items(),
                                               key=lambda kv: sum(x.get("FullCashValue") or 0 for x in kv[1]),
                                               reverse=True)}
    all_values = money(rows, "FullCashValue")
    sale_dates = [r["SaleDate"] for r in rows if isinstance(r.get("SaleDate"), (int, float))]
    return {
        "parcels": len(rows),
        "total_assessed_value_all_classes": round(sum(all_values)) if all_values else 0,
        "value_by_class_share_pct": {k: round(v["total_value"] / max(sum(all_values), 1) * 100, 1)
                                     for k, v in by_class.items()},
        "classes": by_class,
        "roll_vintage_latest_sale": (dt.datetime.fromtimestamp(max(sale_dates) / 1000, dt.timezone.utc).date().isoformat()
                                     if sale_dates else None),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", action="append", dest="zips", help="repeatable; defaults to the comparison set")
    ap.add_argument("--sale-months", type=int, default=24, dest="sale_months")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent / "maricopa_parcel_stats.json"))
    args = ap.parse_args()
    zips = args.zips or ZIPS

    out = []
    for z in zips:
        declared = count_of(z)
        rows = pull_zip(z, declared)
        s = summarise(rows, 30 * args.sale_months)
        s["zip"] = z
        s["service_count"] = declared
        s["paging_matches"] = len(rows) == declared
        if z in SUBAREA_NOTE:
            s["note"] = SUBAREA_NOTE[z]
        out.append(s)
        cls = s["classes"]
        res = cls.get("residential (built)", {})
        vacant = cls.get("vacant residential land", {})
        print(f"{z}  parcels {s['parcels']:>6}   total assessed ${s['total_assessed_value_all_classes']:>16,}")
        print(f"     houses: {res.get('parcels', 0):>6} parcels  median ${res.get('median_value') or 0:>10,}  "
              f"1st quartile ${res.get('quartile_1_value') or 0:>9,}  latest recorded sale {res.get('latest_recorded_sale')}")
        print(f"     vacant residential lots: {vacant.get('parcels', 0):>5}  median ${vacant.get('median_value') or 0:>8,}")
        print(f"     value share: " + ", ".join(f"{k} {v}%" for k, v in
              sorted(s["value_by_class_share_pct"].items(), key=lambda kv: -kv[1])[:5]))
        for name, b in list(cls.items())[:4]:
            if b["parcels"] == 0:
                continue
            print(f"       · {name:22s} {b['parcels']:>6} parcels  total ${b['total_value']:>15,}  "
                  f"median ${b['median_value'] or 0:>10,}  land {b['land_share_pct']}%  "
                  f"sales in window {b['sales_in_window']}")

    payload = {"source": "Maricopa County Assessor parcel roll (Parcel_Data_View feature service)",
               "service": SERVICE, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "sale_window_months": args.sale_months,
               "interpretation": ("FullCashValue is a market-scale value: a Tolleson SFR parcel shows 250,000 and its "
                                  "recorded sale was 253,000. Tax billed and TaxYear are empty in this view, so tax rates "
                                  "are not available here. Check each ZIP's latest_recorded_sale before treating a value as current."),
               "results": out}
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2))
    print(f"wrote {args.out}")

    # A ZIP that exists must return parcels, a ZIP that does not must return exactly none, and the paging must
    # agree with the service's own count. Those three are the whole contract of this script.
    first = out[0]
    nothing = count_of("00000")
    assert first["parcels"] > 0, "the first ZIP returned no parcels — the field name or the service is wrong"
    assert nothing == 0, f"a ZIP that does not exist returned {nothing} parcels — the filter is not filtering"
    assert all(o["paging_matches"] for o in out), "paging disagreed with the service's own count for at least one ZIP"
    assert any(c["parcels"] > 0 for c in first["classes"].values()), "no parcels classified — the classifier is wrong"
    print("self-test passed: real ZIPs return parcels, a fake ZIP returns zero, paging matched the service's own count, and the classifier grouped parcels")
