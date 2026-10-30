# What the two utilities said, and where it is written

Two documents, both filed rather than published: Pinnacle West Capital Corporation's 2025 annual report, which carries
Arizona Public Service's audited report to the SEC (237 pages), and Salt River Project's Joint District
Board and Council packet for its 30 September 2025 meeting, filed with the Commission on 3 November 2025.
Every sentence below was found in the document at the page given — `tools/verify_claims.py` checks that, not my
transcription. These are the parties describing their own plans; that is stated here rather than left for a reader to
work out.

## Arizona Public Service, from its annual report

> “APS projects it will develop 263 miles of new transmission lines over the next 10 years”
>
> — page 66

> “APS plans to upgrade 725 miles of existing transmission lines over the same horizon”
>
> — page 66

> “approximately 5,939 pole miles of overhead lines and approximately 86 miles of underground lines”
>
> — page 65

> “APS also owns and maintains 477 substations”
>
> — page 65

> “Overall sales are expected to increase 5 to 7% per year through 2030”
>
> — page 3

> “Peak demand in 2025 rose more than 5% over the prior year”
>
> — page 4

> “We invested $2.4 billion in new capital in support of reliability and growth”
>
> — page 6

> “deployed more than 1,600 megawatts (MW) of new generation”
>
> — page 3

> “Arizona’s supply of Colorado River water will remain subject to a Tier 1 shortage”
>
> — page 40

> “reduce the generation capacity of thermal-power plants and decrease the efficiency of the transmission grid”
>
> — page 50

> “the Arizona housing market”
>
> — page 51

> “Taiwan Semiconductor Manufacturing Company, Microsoft, Amkor, SMC and others”
>
> — page 3

The facility tables in the same filing are reproduced in `data/aps_capital.json` as the filing prints them, with the
page. The numeric columns after the year are not labelled unambiguously in the extracted text, so no capacity totals
are computed here — a row is a row the company printed, not a figure derived from it.

## Salt River Project, from its own board packet

> “stating that the voltage levels for transmission are 500 kilovolts (kV), 230kV and 69kV”
>
> — page 8, attributed to Zack Heim, SRP Senior Director of Power Delivery

> “They explained that SRP’s transmission network is 1,492 miles with 287 substations”
>
> — page 8, attributed to Zack Heim, SRP Senior Director of Power Delivery

> “stated that the purpose of the presentation was to provide information regarding an overview of SRP’s transmission expansion plans and the Salt River Pumped Storage Project as two key initiatives enabling renewable integration and large-scale load growth”
>
> — page 8, attributed to Zack Heim, SRP Senior Director of Power Delivery

> “They provided a summary of five transmission studies and budget pathways”
>
> — page 9, attributed to Nate Tate, SRP Director of Transmission Planning, Strategy, and Development

> “They presented maps of new transmission projects in the Financial Plan 2026 (FP26) and FP27 budgets and potential future load projects”
>
> — page 9, attributed to Nate Tate, SRP Director of Transmission Planning, Strategy, and Development

> “R. Norlin provided charts showing high voltage transmission growth from the 2035 Transmission Study and the Transitional Load Cluster Study”
>
> — page 9, attributed to Ryan Norlin, SRP Director of Strategic System Projects

> “They described hyperscale substation construction and provided a time-lapse video of substation construction”
>
> — page 9, attributed to Ryan Norlin, SRP Director of Strategic System Projects

> “They discussed a high voltage underground express loop and high voltage transmission line construction, stating that there is an increasing need for new high voltage transmission”
>
> — page 9, attributed to Ryan Norlin, SRP Director of Strategic System Projects

> “SRP will need to more than double, if not triple, resource capacity in the next decade based on sustainability targets and current customer requests”
>
> — page 9, attributed to Craig Larson, SRP Senior Director of Power Generation

> “life cycle costs for battery energy storage systems (BESS) grow faster than pumped hydro energy storage (PHES) over time”
>
> — page 10, attributed to A. Bond-Simpson provided a technology comparison for pumped storage and lithium-ion batteries

> “pumped hydropower energy storage was selected in all 42 cases of the 2023 ISP”
>
> — page 9, attributed to Craig Larson, SRP Senior Director of Power Generation

> “a preliminary timeline for design, permitting, and construction from 2022 to 2036”
>
> — page 10, attributed to Craig Larson, SRP Senior Director of Power Generation

> “Tammi Watson of CAP entered the meeting”
>
> — page 15

> “Area 1: Phoenix, Guadalupe, Tempe, Avondale, Maricopa County, GRIC”
>
> — page 105

> “Data Centers & Energy/Water Supply Nexus”
>
> — page 150

**What was looked for in that document and is not in it:** Goodyear, Avondale substation, Cotton Corridor, Tolleson, Buckeye substation. The packet's project
maps are images, so a place can be in the plan and not in the extractable text. That list is published because the
absence is a fact about the document, not a fact about SRP's plans.

## Reading the two together

Both utilities describe the same driver in different words — APS names specific advanced-manufacturing and data-centre
customers in its filing's risk and outlook sections; SRP's packet records a presentation to its own board about
"large-scale load growth". Neither number is independently corroborated by the other, and neither is a projection of
mine. What is independent is the permitting record in `permitted-corridors.md`: applications by these same parties,
and decisions with dates and numbers attached.
