"""Land values around the substations, snapshotted today so a later run can report the change.

The outlook document makes one prediction that is directly testable against the county's own roll: land near a
named substation or storage project revalues before land that is merely nearby, and before the houses do. That
prediction is worthless without a baseline, and the baseline has to be taken before the thing it is waiting for
(White Tank, Avondale, dated 2027) exists. So this takes it.

Three points, each measured as a 2 km-wide and a 4 km-wide square of parcels:
  - Rudd substation — APS 500/230 kV, OSM way 105031253, 12100 W Broadway: the site already energised, three
    hundred metres from Alamar Park.
  - Orme substation — SRP 230 kV distribution, OSM way 86377610, 3032 S 59th Ave: a second, different operator,
    already-built comparison.
  - An offset control — 3.5 km from Rudd in the same ZIP, no facility named in any filing I have read. Same
    school districts, same water district, nothing being built.

The comparison that matters is not "is land near a substation expensive", it is the ratio between the near
buffer and the control buffer, today, and what happens to that ratio in 2027 and 2028. The centroids come from
OpenStreetMap primitives (a way's own node coordinates), not from a geocoder, because a geocoder could not find
these places at all.

Run:  python3 monitor.py            # writes baselines/spatial-<date>.json
      python3 monitor.py --diff     # pulls fresh and prints deltas against the newest baseline
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import math
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from maricopa_parcel_stats import FIELDS, classify, get, summarise  # the same reader the property ledger uses

# Acreage and construction year are what make the comparison mean anything: a $6,200 parcel and a $77,700 parcel
# are the same price per acre if one is an acre and the other is twelve, and a house-value comparison between
# neighbourhoods of different vintage is not a comparison at all. The county carries both, so both are asked for.
MONITOR_FIELDS = FIELDS + ",LotSize_Acre,LivableArea_SqFt,ConstructionYear,LandLegalClassCode,LandLegalClassDescription"

BASELINES = HERE.parent / "baselines"
HALF_KM = [1.0, 2.0]  # half-widths of the square, in km

TARGETS = [
    {"name": "Rudd substation", "detail": "APS 500/230 kV, OSM way 105031253, 12100 W Broadway, Avondale",
     "lat": 33.40923, "lon": -112.31778, "kind": "substation"},
    {"name": "Orme substation", "detail": "SRP 230 kV distribution, OSM way 86377610, 3032 S 59th Ave, Phoenix",
     "lat": 33.42055, "lon": -112.18794, "kind": "substation"},
    {"name": "offset control", "detail": "3.5 km north-west of Rudd in the same ZIP; no facility named in any "
                                          "filing read for this project", "lat": 33.43506, "lon": -112.35090,
     "kind": "control"},
]
# Known-false case: the roll covers Maricopa County only, so a point in Colorado must return nothing. If a
# spatial query returned parcels there, the geometry parameter is being ignored and every number here is fake.
NEGATIVE_POINT = {"name": "off-county control", "lat": 40.0150, "lon": -105.2705}

DATASETS = ["maricopa_parcel_stats.json", "census_city_profile_2023_acs5.json", "tax_rates.json",
            "aps_capital.json"]


def box_km(target: dict, half_km: float) -> str:
    """A square around the point, in degrees. This service rejects `distance`/`units` on a point query but
    answers an envelope in WGS84, so the buffer is a square: a 2 km half-width is 4 km across, the same shape
    for every target and for the control, which is what makes the ratio between them meaningful."""
    dlat = half_km / 111.32
    dlon = half_km / (111.32 * math.cos(math.radians(target["lat"])))
    return json.dumps({"xmin": round(target["lon"] - dlon, 6), "ymin": round(target["lat"] - dlat, 6),
                       "xmax": round(target["lon"] + dlon, 6), "ymax": round(target["lat"] + dlat, 6),
                       "spatialReference": {"wkid": 4326}})


def buffered_query(target: dict, half_km: float) -> list[dict]:
    base = {"geometry": box_km(target, half_km), "geometryType": "esriGeometryEnvelope",
            "relation": "esriSpatialRelIntersects", "where": "1=1",
            "outFields": MONITOR_FIELDS, "returnGeometry": "false", "f": "json"}
    expected = int(get({**base, "returnCountOnly": "true"}).get("count", 0))
    rows, offset = [], 0
    while True:
        d = get({**base, "resultRecordCount": 2000, "resultOffset": offset})
        feats = d.get("features", [])
        if not feats:
            break
        rows.extend(f["attributes"] for f in feats)
        offset += len(feats)
        if offset >= expected or len(feats) < 2000:
            break
    assert len(rows) == expected, f"paged {len(rows)} parcels where the service reported {expected}"
    return rows


def land_and_vintage(rows: list[dict]) -> dict:
    """Vacant land priced per acre, the acreage distribution, and the vintage of the built housing nearby.

    Only parcels the county carries an acreage for are counted, and that count is reported: if most parcels in
    one box had no acreage, the median describes the parcels that do, not the box. The median construction year
    is here so the house comparison cannot be read as a neighbourhood effect when it is a vintage effect.
    """
    out = {}
    for cls in ("vacant residential land", "other vacant land"):
        dollars_per_acre, acres = [], []
        for r in rows:
            if classify(r) != cls:
                continue
            acre = r.get("LotSize_Acre")
            value = r.get("FullCashValue")
            if isinstance(acre, (int, float)) and acre > 0.05 and isinstance(value, (int, float)) and value > 0:
                dollars_per_acre.append(value / acre)
                acres.append(acre)
        out[cls] = {"with_acreage": len(dollars_per_acre),
                    "median_dollars_per_acre": round(statistics.median(dollars_per_acre)) if dollars_per_acre else None,
                    "median_acres": round(statistics.median(acres), 2) if acres else None}
    # The county's own land legal class is the designation the analysis is about, and it is better read than
    # inferred: which use a parcel is legally carrying is a field, not something to guess from its price.
    classes: dict[str, list] = {}
    for r in rows:
        key = str(r.get("LandLegalClassDescription") or "unclassified")[:48]
        classes.setdefault(key, []).append((r.get("FullCashValue"), r.get("LotSize_Acre")))
    legal = []
    for key, vals in classes.items():
        worth = [v for v, _ in vals if isinstance(v, (int, float)) and v > 0]
        per_acre = sorted(v / a for v, a in vals
                          if isinstance(v, (int, float)) and v > 0 and isinstance(a, (int, float)) and a > 0.05)
        acres = sorted(a for _, a in vals if isinstance(a, (int, float)) and a > 0.05)
        legal.append({"land legal class": key, "parcels": len(vals),
                      "median value": round(statistics.median(worth)) if worth else None,
                      "median $/acre": round(statistics.median(per_acre)) if per_acre else None,
                      "median acres": round(statistics.median(acres), 2) if acres else None})
    legal.sort(key=lambda x: -x["parcels"])
    out["land legal classes"] = legal[:8]
    built = [r.get("ConstructionYear") for r in rows
             if classify(r) == "residential (built)" and isinstance(r.get("ConstructionYear"), (int, float))
             and r["ConstructionYear"] > 1800]
    out["residential built: parcels with a construction year"] = len(built)
    out["residential built: median construction year"] = int(statistics.median(built)) if built else None
    return out


def snapshot() -> dict:
    out = {"taken": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "boxes_km": HALF_KM,
           "how_to_read": "a buffer is every parcel the assessor holds inside a square of that half-width, in "
                          "WGS84 degrees (this service refuses distance/units on a point query but answers an "
                          "envelope). Medians are FullCashValue, which is this year's county valuation, not a "
                          "sale price. Land is also expressed per acre, and the median construction year of the "
                          "nearby housing is recorded so a value difference cannot be read as a location effect "
                          "when it is a vintage effect.",
           "targets": [], "negative_control": {}, "dataset fingerprints": {}}
    for t in TARGETS:
        entry = {k: v for k, v in t.items()}
        entry["buffers"] = {}
        for r in HALF_KM:
            rows = buffered_query(t, r)
            detail = land_and_vintage(rows)
            entry["buffers"][str(r)] = {"parcels": len(rows), **summarise(rows, sale_window_days=730),
                                        "land and vintage": detail}
            land = detail["vacant residential land"]
            print(f"  {t['name'][:18]:<18} r={r} km half-width: {len(rows)} parcels | vacant land "
                  f"{land['median_dollars_per_acre']} $/ac over {land['with_acreage']} parcels "
                  f"(median lot {land['median_acres']} ac) | houses built ~{detail['residential built: median construction year']}",
                  flush=True)
        out["targets"].append(entry)
    neg = buffered_query(NEGATIVE_POINT, 2.0)
    out["negative_control"] = {"point": NEGATIVE_POINT, "parcels": len(neg)}
    print(f"  off-county control (must be 0): {len(neg)} parcels", flush=True)
    for name in DATASETS:
        p = HERE / name
        if p.exists():
            out["dataset fingerprints"][name] = {"bytes": p.stat().st_size,
                                                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true", help="pull fresh and compare with the newest baseline")
    args = ap.parse_args()
    BASELINES.mkdir(parents=True, exist_ok=True)

    fresh = snapshot()
    today = dt.date.today().isoformat()
    if not args.diff:
        dest = BASELINES / f"spatial-{today}.json"
        dest.write_text(json.dumps(fresh, indent=2))
        print(f"wrote {dest}")
        for t in fresh["targets"]:
            for r, b in t["buffers"].items():
                cls = b.get("classes", {})
                med = cls.get("residential (built)", {}).get("median_value")
                vac = cls.get("vacant residential land", {}).get("median_value")
                print(f"  {t['name'][:18]:<18} r={r}: houses median {med}  vacant residential median {vac}")
        return 0

    prior_files = sorted(BASELINES.glob("spatial-*.json"))
    if not prior_files:
        raise SystemExit("no baseline to compare against; run without --diff first")
    prior = json.loads(prior_files[-1].read_text())
    print(f"comparing against {prior_files[-1].name} taken {prior['taken']}")
    for now_t, was_t in zip(fresh["targets"], prior["targets"]):
        for r in map(str, HALF_KM):
            a, b = now_t["buffers"][r], was_t["buffers"][r]
            print(f"\n{now_t['name']} at {r} km: parcels {b['parcels']} -> {a['parcels']} "
                  f"({a['parcels'] - b['parcels']:+d})")
            for cls in ("residential (built)", "vacant residential land", "warehousing", "data centre",
                        "industrial"):
                na = a.get("classes", {}).get(cls, {})
                nb = b.get("classes", {}).get(cls, {})
                if not na and not nb:
                    continue
                ma, mb = na.get("median_value"), nb.get("median_value")
                if ma is None or mb is None:
                    print(f"  {cls}: {mb} -> {ma}")
                    continue
                delta = round(100 * (ma / mb - 1), 1)
                print(f"  {cls}: median {mb:,} -> {ma:,} ({delta:+.1f}%)  parcels {nb.get('parcels')} -> "
                      f"{na.get('parcels')}")
    (BASELINES / f"spatial-{today}.json").write_text(json.dumps(fresh, indent=2))
    print(f"\nwrote {BASELINES / f'spatial-{today}.json'}")
    return 0


if __name__ == "__main__":
    rc = main()
    report = json.loads((BASELINES / f"spatial-{dt.date.today().isoformat()}.json").read_text())
    near = report["targets"][0]["buffers"]["2.0"]
    assert near["parcels"] > 0, "the 4 km-wide box at an energised substation found no parcels — the reader is blind"
    assert report["negative_control"]["parcels"] == 0, "a buffer in Colorado returned Maricopa parcels: the geometry parameter is being ignored"
    for t in report["targets"]:
        assert t["buffers"]["1.0"]["parcels"] <= t["buffers"]["2.0"]["parcels"], "a smaller box held more parcels"
    print(f"self-test passed: {near['parcels']} parcels within 2 km of Rudd, 0 within 2 km of a point in "
          f"Colorado, and every 1 km buffer is a subset of its 2 km buffer")
    sys.exit(rc)
