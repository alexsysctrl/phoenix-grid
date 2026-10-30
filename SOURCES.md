# Sources

Every number in this repository comes from one of the documents below. They are listed with the address they were
fetched from, the date, and the sha256 of the file as fetched, so any claim can be checked against the original rather
than against this summary. The bulk files (two utility filings, several filed PDFs) are not shipped here because of
their size; the hashes are what you would get if you fetched them from the address given.

The derived datasets that *are* shipped — `data/*.json` — are produced by the scripts that sit beside them. Running a
script again re-reads the source and rewrites its JSON; the self-test inside each script asserts specific facts about
its own output.

## Regulator records

| what | where it came from | read on | sha256 of what was fetched |
|---|---|---|---|
| Siting-hearing calendar — the Arizona Power Plant and Transmission Line Siting Committee's own schedule of hearings and meetings | `https://www.azcc.gov/arizona-power-plant/hearings-and-meetings` | 28 October 2026 | `8fb7e8e0b534e1e8e612aa2fe95d7fdf082a34b69411562c97d3857f030df9de` |
| Docket records for the applications on that calendar — status, filing date, every decision with its number, type and date | Arizona Corporation Commission eDocket API, `https://efiling.azcc.gov/api/edocket/` (`data/acc_dockets.py`) | 28 October 2026 18:27 MST | responses kept per-docket; the joined result is `data/acc_dockets.json` |
| The texts of the Commission's decisions themselves, 76 of them, each identified by the Commission's own file number | `https://docket.images.azcc.gov/` (`data/acc_decisions.py`) | 29 October 2026 | listed per decision in `decisions/index.json` |
| Transcript of the Case 248 hearing, Volume I — 175 pages, heard in Avondale on 29 September 2025 | the Commission's document host for docket `L-21304A-25-0169-00248` | 28 October 2026 | `e16cb2ffed721d04459ff756f403fa2c260bdaf811529d9953bfc242ae8ca781` |
| Maricopa County Board of Supervisors, Planning & Zoning agenda, 10 December 2025 — 19 pages | `https://www.maricopa.gov/AgendaCenter/ViewFile/Item/10030?fileID=97132` | 29 October 2026 | PDF `0cd814709a04389bcf473420112e6bc6acf3fa4bf0c1bb0a608213be249a2160`, extracted text `160d04a22817b409b53c532d56ad68564773c428f47daf6355654cf7bda79aa4` |
| The same agenda, 8 April 2026 — 11 pages | `https://www.maricopa.gov/AgendaCenter/ViewFile/Item/10227?fileID=100092` | 29 October 2026 | see `data/apr2026-consent-cases.json`, which carries both hashes |

## Utility filings

| what | where it came from | read on | sha256 |
|---|---|---|---|
| Pinnacle West Capital Corporation 2025 Annual Report — the document carrying Arizona Public Service's audited annual report to the SEC, 237 pages. The source of the transmission mileages, the capital figure, the jointly-owned system table and the named facility tables | `https://s22.q4cdn.com/464697698/files/doc_financials/2025/ar/PNW_2025_Annual_Report_.pdf` | 28 October 2026 | `34641dac88bf4d95d6896c68e1bc21ccce91601ed518778ba3aea6bdb6de0afb` |
| Salt River Project Joint District Board and Council board packet, meeting of 30 September 2025, 167 pages, filed with the Commission on 3 November 2025 | `https://www.srpnet.com/v3/assets/bltefc1fc708dcc94e7/bltd7bd181b284cfca4/20251103_DB_packet.pdf` | 28 October 2026 | `b241a194e6c24ff0fa205bbf711afc40569b2181eaf5649e5474152660478950` |
| The Harquahala Sun project page (Copia Power), including its list of Commission decision numbers | `https://harquahalasun.com` | 28 October 2026 | `268b2b1ed242f4398acd0233d6bf3a789a042b3661b3fc3deba01a0d7afb5087` |

## Land, tax and household data

| what | where it came from | read on |
|---|---|---|
| Maricopa County Assessor parcel roll, 2026 — assessed values, land and improvement splits, lot areas, construction years, recorded sale dates | ArcGIS feature service `https://services.arcgis.com/ykpntM6e3tHvzKRJ/arcgis/rest/services/Parcel_Data_View/FeatureServer/0` (`data/maricopa_parcel_stats.py`, `data/sale_timeseries.py`, `data/monitor.py`) | 28 October 2026 |
| Maricopa County property tax rate table, 2025 | `https://www.maricopa.gov/DocumentCenter/View/109591/Tax-Rate-2025-PDF` | 28 October 2026, sha256 `335b498ac19e90ca1827381e122c55bcbd4195edd83f80397619abce6f613fe1` |
| Arizona Department of Revenue transaction privilege tax rate table, effective 1 June 2026 | `https://azdor.gov/sites/default/files/document/TPT_RATETABLE_06012026.pdf` | 28 October 2026, sha256 `b30dc3948292da902d015e59fc76a3d18027c77ba03df2af07c4cf811aeaa3dc` |
| Census Bureau American Community Survey, 2023 5-year estimates, for 35 municipalities in the metro | `https://api.census.gov/data/` (`data/census_city_profile.py`) | 28 October 2026 |

## What is *not* a source here

No press release, no news article, and no third-party summary is used as evidence for a claim about a permit, a
mileage, a capacity or a decision date. Where a company describes itself — a project page, a filing's narrative
section — the description is quoted and attributed as the company's own statement, and the decision numbers it cites
are checked against the regulator's docket records instead. Two dates on a developer's project page disagreed with the
Commission's own records for the same decisions; `permitted-corridors.md` uses the Commission's dates and says so.
