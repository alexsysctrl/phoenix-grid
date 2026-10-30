#!/usr/bin/env python3
"""City-level social and housing economics for the Phoenix West Valley, from the Census ACS.

The assessor roll describes what the buildings are worth. This describes who lives in them and what they pay:
population, household income, earnings, housing values, gross rents, vacancy, tenure, and how new the housing
stock is. Both scales are needed: the assessor gives ZIP-level property
structure, the ACS gives city-level people and income, because the ACS no longer publishes ZCTA geography
through the API (verified: zcta5cd is rejected by every ACS vintage I tried, though the geography page lists
"zip code tabulation area").

  python3 census_city_profile.py                 2023 five-year, the West Valley plus comparison metros
  python3 census_city_profile.py --vintage 2023 --dataset acs5
  python3 census_city_profile.py --dataset acs1   the one-year estimates, more current, smaller samples

The API key comes from CENSUS_API_KEY in the environment, or from the stack vault on the machine that has one
configured; never from a file on disk. Place GEOIDs come from
the API itself (place:* within a state) rather than from a gazetteer download, because a mistyped GEOID
silently returns a different city.

Variables are split across two datasets on purpose: B-tables for population and income, the DP04 profile for
value, rent, vacancy and structure age. Both were tested against the API before being listed here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import urllib.parse
import urllib.request

UA = "alex-sqopa-research/1.0 (alex@sqopa.com)"
VAULT_NAME = "census.api-key"

MAIN_VARS = {
    "B01003_001E": "population",
    "B19013_001E": "median household income",
    "B19301_001E": "median family income",
    "B19080_001E": "mean household income",
    "B06011_001E": "median wages employed civilians",
}
PROFILE_VARS = {
    "DP04_0001E": "housing units",
    "DP04_0002E": "occupied units",
    "DP04_0003E": "vacant units",
    "DP04_0004PE": "homeowner vacancy percent",
    "DP04_0005PE": "rental vacancy percent",
    "DP04_0007PE": "percent one-unit detached",
    "DP04_0017PE": "percent built 2020 or later",
    "DP04_0018PE": "percent built 2010 to 2019",
    "DP04_0046E": "owner occupied units",
    "DP04_0047E": "renter occupied units",
    "DP04_0089E": "median home value",
    "DP04_0101E": "median monthly owner cost with mortgage",
    "DP04_0134E": "median gross rent",
    "DP03_0088E": "per capita income",
    "DP03_0092E": "median earnings for workers",
    "DP03_0128PE": "percent of people below poverty",
}

# The West Valley as one economy, plus the places worth comparing it against.
STATES = {
    "04": ["Avondale", "Buckeye", "Goodyear", "Tolleson", "Litchfield Park", "El Mirage", "Surprise",
           "Phoenix", "Glendale", "Peoria", "Queen Creek", "Gilbert", "Mesa", "Chandler", "San Luis",
           "Bullhead City", "Tucson", "Marana", "Sahuarita", "Casa Grande", "Apache Junction"],
    "06": ["Riverside", "Ontario", "Victorville"],
    "48": ["Dallas", "Frisco", "Georgetown", "Austin"],

    "37": ["Charlotte", "Huntersville"],
    "17": ["Chicago", "Joliet"],
    "53": ["Seattle", "Kent"],
    "13": ["Sandy Springs"],
    "39": ["Columbus"],
    "08": ["Denver", "Aurora"],
    "29": ["Kansas City"],
    "12": ["Orlando", "Kissimmee", "Tampa"],
}


def api_key() -> str:
    """The Census API key. From the environment if it is there, so this script runs anywhere; from the stack
    vault on the machine that has one configured. Neither is required to read the datasets this script wrote."""
    env = os.environ.get("CENSUS_API_KEY")
    if env:
        return env
    return vault_secret(VAULT_NAME)


def vault_secret(name: str) -> str:
    raise SystemExit("no Census API key: set CENSUS_API_KEY in the environment")

def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read().decode())
    if isinstance(body, dict):
        raise RuntimeError(f"census API error: {body}")
    return body


def rows_to_dicts(body) -> list[dict]:
    header = body[0]
    return [dict(zip(header, row)) for row in body[1:]]


def acql(url: str) -> str:
    return urllib.parse.quote(url, safe="")


def place_directory(state_fips: str, vintage: int, dataset: str, key: str) -> dict[str, str]:
    """City name -> place GEOID, from the API rather than a gazetteer file."""
    body = fetch_json(f"https://api.census.gov/data/{vintage}/acs/{dataset}"
                      f"?get=NAME&for=place:*&in=state:{state_fips}&key={key}")
    out: dict[str, str] = {}
    for rec in rows_to_dicts(body):
        name = str(rec.get("NAME", "")).split(",")[0]
        for suffix in (" CDP", " city", " town", " village"):
            name = name.replace(suffix, "")
        out.setdefault(name.strip().upper(), rec.get("place"))
    return out


def pull_dataset(vintage: int, dataset: str, subdataset: str, state_fips: str, geoids: list[str],
                 variables: dict, key: str) -> dict[str, dict]:
    """One query for every place in a state, then keep only the ones asked for.

    The API rejects a comma-separated list of place GEOIDs; place:* inside a state is accepted, so the filter
    happens here instead. Same data, fewer syntax games.
    """
    get = "NAME," + ",".join(variables)
    url = (f"https://api.census.gov/data/{vintage}/acs/{dataset}{subdataset}?get={acql(get)}"
           f"&for=place:*&in=state:{state_fips}&key={key}")
    wanted = set(geoids)
    merged: dict[str, dict] = {}
    for rec in rows_to_dicts(fetch_json(url)):
        if rec.get("place") in wanted:
            merged.setdefault(rec.get("place"), {}).update(rec)
    return merged


def _no_duplicate_states() -> None:
    """Fail loudly if STATES ever contains the same state FIPS twice.

    Python evaluates a dict literal with duplicate keys by keeping the last one, so a second "12": [...] entry
    silently deletes the first. That is how Orlando and Kissimmee vanished from a run that reported nothing.
    """
    import ast
    tree = ast.parse(pathlib.Path(__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(x, "id", "") == "STATES" for x in node.targets):
            keys = [k.value for k in node.value.keys]
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            if dupes:
                raise AssertionError(f"STATES has duplicate state keys {dupes}: the earlier city lists are being discarded")
            return
    raise AssertionError("STATES not found in this file — the check cannot run")


if __name__ == "__main__":
    _no_duplicate_states()
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", type=int, default=2023)
    ap.add_argument("--dataset", default="acs5", choices=["acs5", "acs1"])
    args = ap.parse_args()
    out_path = pathlib.Path(__file__).resolve().parent / f"census_city_profile_{args.vintage}_{args.dataset}.json"

    key = api_key()
    results, not_found = [], []
    for st, names in STATES.items():
        directory = place_directory(st, args.vintage, args.dataset, key)
        geoids = []
        for n in names:
            g = directory.get(n.upper())
            if not g:
                not_found.append(f"{st}:{n}")
                continue
            geoids.append(g)
        if not geoids:
            continue
        main = pull_dataset(args.vintage, args.dataset, "", st, geoids, MAIN_VARS, key)
        profile = pull_dataset(args.vintage, args.dataset, "/profile", st, geoids, PROFILE_VARS, key)
        for geoid, rec in main.items():
            row = {"name": rec.get("NAME"), "place_geoid": geoid, "state_fips": st,
                   "vintage": args.vintage, "dataset": args.dataset}
            for var, label in {**MAIN_VARS, **PROFILE_VARS}.items():
                raw = (rec | profile.get(geoid, {})).get(var)
                if raw in (None, "", "N", "null"):
                    row[label] = None
                else:
                    row[label] = float(raw) if label.endswith("percent") or "percent" in label else int(raw)
            units = row.get("housing units") or 0
            vacant = row.get("vacant units") or 0
            row["vacancy rate percent"] = round(vacant / units * 100, 2) if units else None
            owned = row.get("owner occupied units") or 0
            occ = row.get("occupied units") or 0
            row["owner share of occupied percent"] = round(owned / occ * 100, 1) if occ else None
            value = row.get("median home value")
            income = row.get("median household income")
            row["value to income ratio"] = round(value / income, 2) if value and income else None
            rent = row.get("median gross rent")
            row["annual rent as share of median income percent"] = round(rent * 12 / income * 100, 1) if rent and income else None
            results.append(row)

    results.sort(key=lambda r: (r.get("population") or 0), reverse=True)
    cols = ["population", "median household income", "median wages employed civilians", "median home value",
            "median gross rent", "value to income ratio", "annual rent as share of median income percent",
            "vacancy rate percent", "percent built 2020 or later", "owner share of occupied percent"]
    print(f"{'place':34}" + "".join(f"{c[:17]:>18}" for c in cols))
    for r in results:
        line = f"{str(r['name'])[:34]:34}"
        for c in cols:
            v = r.get(c)
            line += f"{('%.1f' % v) if isinstance(v, float) else (v if v is not None else 'n/a'):>18}"
        print(line)
    if not_found:
        print("NOT FOUND:", ", ".join(not_found))

    payload = {"source": f"US Census Bureau ACS {args.vintage} {args.dataset} (data + profile) via api.census.gov",
               "main_variables": MAIN_VARS, "profile_variables": PROFILE_VARS,
               "derived": {"vacancy rate percent": "vacant units / housing units",
                           "owner share of occupied percent": "owner occupied / occupied",
                           "value to income ratio": "median home value / median household income",
                           "annual rent as share of median income percent": "median gross rent x 12 / median household income"},
               "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "not_found": not_found, "results": results}
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out_path}")

    # Self-test: Avondale must appear with a plausible population, and a fake GEOID must return nothing.
    avondale = next((r for r in results if "Avondale" in str(r.get("name"))), None)
    assert avondale, "Avondale was not returned — the place directory or the API call is wrong"
    assert 50_000 < (avondale.get("population") or 0) < 200_000, \
        f"Avondale population {avondale.get('population')} is outside the plausible range (about 90k in 2020 census)"
    fake = pull_dataset(args.vintage, args.dataset, "", "04", ["0000000000"], MAIN_VARS, key)
    assert not fake, "a nonexistent place GEOID returned data — the filter is not filtering"
    print("self-test passed: Avondale returned a plausible population, a fake GEOID returned nothing")
