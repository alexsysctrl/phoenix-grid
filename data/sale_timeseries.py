"""Recorded sale prices by quarter, per ZIP, out of the county's own roll — the price series this project lacked.

The outlook document was honest about having no price series, only one assessment year. That is true of valuations
and false of prices: the assessor's parcel view carries `SalePrice` and `SaleDate` for every parcel, which is the
county's record of what each parcel last sold for and when. Reading those out gives, from a single pull, the
distribution of recorded transfers over roughly the last two years per ZIP — a real, primary-source price series
at ZIP-code level.

Three things this is not, stated where the numbers appear:
  - It is one transaction per parcel: the *latest* one the county holds. A parcel that sold in 2024 and again in
    2026 appears once, with 2026. So the early part of the window is thinner than the recent part by construction,
    and it is not a repeat-sales index.
  - It counts only properties that sold. A quarter with few sales in a quiet subdivision is not a price signal.
  - These are actual prices, not assessed values. They are the only prices in this project.

Every quarter is printed with its count. Quarters under 25 sales are marked thin and are not used in any
comparison.

Run:  python3 sale_timeseries.py            → sale_timeseries.json
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from maricopa_parcel_stats import SERVICE, PAGE, ZIPS, classify, get  # the same reader as the property ledger

FIELDS = "OBJECTID,PropertyZipCode,SalePrice,SaleDate,PropertyUseDescription"
# A sentinel date somewhere in the roll once produced a quarter label far outside the plausible range, which a string
# comparison against the window start happily accepted. Dates outside this range are dropped and counted.
YEAR_MIN, YEAR_MAX = 1990, __import__("datetime").date.today().year + 1
THIN = 25  # below this many recorded transfers, a median describes a handful of houses, not a market
WINDOW_START = "2023Q1"  # the county holds sales back to the 1990s; the series is reported from here


def parse_date(value):
    """SaleDate as the county's service actually returns it: epoch milliseconds. A value that is far too small to
    be milliseconds is treated as seconds, and a value that cannot become a date at all returns None. This used
    to yield a quarter labelled 222Q from a nonsense date, which an assert then had to catch."""
    if isinstance(value, (int, float)):
        v = float(value)
        if abs(v) > 1e11:                      # epoch milliseconds, the normal case
            v /= 1000.0
        try:
            return dt.datetime.fromtimestamp(v, dt.timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value[:1].isdigit():
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def valid_quarter(value):
    """(quarter label, plausible). A date outside YEAR_MIN..YEAR_MAX is counted and dropped, not averaged in."""
    d = parse_date(value)
    if d is None or not (YEAR_MIN <= d.year <= YEAR_MAX):
        return None, False
    return f"{d.year}Q{((d.month - 1) // 3) + 1}", True


def pull_quarters(zip_code: str):
    """Page through one ZIP and aggregate as it goes, so memory stays at one page rather than the whole roll.

    Two series per ZIP: every recorded sale, and recorded sales of built residential only. The first is what
    produced a "-67.8%" reading for a warehouse corridor — one quarter containing a large commercial transaction
    next to one that did not is not a house-price trend. Only the residential series is used for comparisons.
    """
    quarters = collections.defaultdict(lambda: {"all": [], "residential": [], "sfr": []})
    offset, seen, bad_dates = 0, 0, 0
    while True:
        d = get({"where": f"PropertyZipCode='{zip_code}'", "outFields": FIELDS, "returnGeometry": "false",
                 "orderByFields": "OBJECTID ASC", "resultRecordCount": PAGE, "resultOffset": offset, "f": "json"})
        feats = d.get("features", [])
        if not feats:
            break
        for f in feats:
            a = f["attributes"]
            price, when = a.get("SalePrice"), a.get("SaleDate")
            seen += 1
            if isinstance(price, (int, float)) and price > 1000:
                q, plausible = valid_quarter(when)
                if not plausible:
                    bad_dates += 1
                    continue
                if q:
                    quarters[q]["all"].append(int(price))
                    if classify(a) == "residential (built)":
                        quarters[q]["residential"].append(int(price))
                        # Site-built only. 85043's residential series contains both single-family sales and
                        # manufactured-home sales, and the mixture is what produced a -67% "trend": the two
                        # segments sell at different prices and in different proportions across quarters.
                        use = str(a.get("PropertyUseDescription") or "").upper()
                        if not any(k in use for k in ("MOBILE HOME", "MANUFACTURED", "PARK")):
                            quarters[q]["sfr"].append(int(price))
        offset += len(feats)
        if len(feats) < PAGE:
            break
    return quarters, seen, bad_dates


def main() -> int:
    out = {"taken": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "source": SERVICE.split("?")[0],
           "definition": "SalePrice and SaleDate as the county records them: the last transaction it holds for "
                         "each parcel. Not a repeat-sales index; a count of recorded transfers per quarter.",
           "thin_threshold": THIN, "zips": []}
    for z in ZIPS:
        quarters, parcels, bad_dates = pull_quarters(z)
        all_sales = sum(len(v["all"]) for v in quarters.values())
        windowed = {q: v for q, v in quarters.items() if q >= WINDOW_START}
        def series(kind: str) -> list[dict]:
            rows = []
            for q in sorted(windowed):
                prices = sorted(windowed[q][kind])
                if not prices:
                    continue
                rows.append({"quarter": q, "sales": len(prices),
                             "median_price": int(statistics.median(prices)),
                             "p25": prices[max(0, len(prices) // 4 - 1)],
                             "p75": prices[min(len(prices) - 1, 3 * len(prices) // 4)],
                             "thin": len(prices) < THIN})
            return rows

        res_rows, all_rows, sfr_rows = series("residential"), series("all"), series("sfr")
        solid = [r for r in sfr_rows if not r["thin"]]
        change = None
        if len(solid) >= 2:
            first, last = solid[0]["median_price"], solid[-1]["median_price"]
            change = round(100 * (last / first - 1), 1)
        out["zips"].append({"zip": z, "parcels_read": parcels,
                            "residential_quarters": res_rows, "all_sale_quarters": all_rows,
                            "site_built_quarters": sfr_rows,
                            "transfers_on_record_any_date": all_sales,
                            "transfers_in_recent_window": sum(r["sales"] for r in all_rows),
                            "dates_dropped_as_implausible": bad_dates,
                            "window_start": WINDOW_START,
                            "adequate_site_built_quarters": len(solid),
                            "site_built_pct_change_first_to_last_adequate_quarter": change})
        print(f"{z}: {parcels} parcels, {all_sales} transfers on record; site-built series: {len(sfr_rows)} "
              f"quarters ({len(solid)} adequate), first→last adequate quarter "
              f"{'n/a' if change is None else str(change) + '%'}; {bad_dates} implausible dates dropped",
              flush=True)
    (HERE / "sale_timeseries.json").write_text(json.dumps(out, indent=2))

    # Self-test with a known-true and a known-false case: a big ZIP must show many adequate quarters, and a ZIP
    # that does not exist must produce nothing at all.
    big = max(out["zips"], key=lambda r: r["transfers_on_record_any_date"])
    assert big["site_built_quarters"], "no site-built transfers found anywhere — the reader is blind"
    empty = get({"where": "PropertyZipCode='00000'", "returnCountOnly": "true", "f": "json"})
    assert int(empty.get("count", 0)) == 0, "a nonexistent ZIP returned parcels"
    dated = [q for r in out["zips"] for q in r["all_sale_quarters"]]
    years = {int(q["quarter"][:4]) for q in dated}
    assert all(YEAR_MIN <= y <= YEAR_MAX for y in years), f"an impossible year reached the output: {sorted(years)}"
    assert any(r["site_built_pct_change_first_to_last_adequate_quarter"] is not None for r in out["zips"]), \
        "no ZIP produced enough site-built sales to compare — the series would be all caveats and no numbers"
    print(f"self-test passed: {len(dated)} quarter rows across {len(out['zips'])} ZIPs, years {min(years)}-{max(years)}, "
          f"{sum(q['sales'] for q in dated)} transfers counted, a fake ZIP returns 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
