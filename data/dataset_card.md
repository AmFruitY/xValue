# Dataset Card — xValue

> **Coverage:** Most datasets span from **2010 to the latest available season**. We are actively sourcing additional data to better describe and predict player transfer values.

---

## File Naming Convention

Applies to both `.py` scraper scripts and `.csv` output files:

```
{source}_{stats|trvalue}_{allplayers|u23players}.{ext}
```

| Segment | Values | Description |
|---|---|---|
| `source` | `fbref`, `understat`, `transfermarkt`, … | Data provider |
| `stats` / `trvalue` | `stats`, `trvalue` | Statistical data or transfer/market value data |
| `allplayers` / `u23players` | `allplayers`, `u23players` | Player age scope |
| `ext` | `py`, `csv` | Script or output file |

**Examples:** `fbref_stats_allplayers.csv`, `transfermarkt_trvalue_allplayers.csv`, `understat_stats_u23players.py`

---

## Statistical Football Data

### FBRef

**Player Seasonal Statistics**

Per-player, per-season aggregated stats across the top 5 European leagues.

| Column | Description |
|---|---|
| `league`, `season`, `team`, `player` | Identifiers |
| `nation`, `pos`, `age`, `born` | Profile |
| `MP`, `Starts`, `Min`, `90s` | Playing time |
| `Gls`, `Ast`, `G+A`, `G-PK`, `PK`, `PKatt` | Goal contributions |
| `CrdY`, `CrdR` | Disciplinary |
| `Gls`, `Ast`, `G+A`, `G-PK`, `G+A-PK` | Per-90 goal contributions |
| `Sh`, `SoT`, `SoT%`, `Sh/90`, `SoT/90`, `G/Sh`, `G/SoT` | Shooting |
| `Mn/MP`, `Min%`, `Mn/Start`, `Compl`, `Subs`, `Mn/Sub`, `unSub` | Substitution & availability |
| `PPM`, `onG`, `onGA`, `+/-`, `+/-90`, `On-Off` | Team impact |
| `2CrdY`, `Fls`, `Fld`, `Off`, `Crs`, `Int`, `TklW` | Defensive & misc |
| `PKwon`, `PKcon`, `OG` | Penalties & own goals |

**Match Statistics (per game)**

Individual player performance logged per match.

| Column | Description |
|---|---|
| `league`, `season`, `game`, `game_id`, `date` | Match identifiers |
| `team`, `player`, `jersey_number`, `nation`, `pos`, `age`, `min` | Player identifiers |
| `Performance_Gls`, `Performance_Ast`, `Performance_PK`, `Performance_PKatt` | Goal contributions |
| `Performance_Sh`, `Performance_SoT` | Shooting |
| `Performance_CrdY`, `Performance_CrdR` | Disciplinary |
| `Performance_Fls`, `Performance_Fld`, `Performance_Off`, `Performance_Crs` | Defensive & misc |
| `Performance_TklW`, `Performance_Int`, `Performance_OG` | Defending |
| `Performance_PKwon`, `Performance_PKcon` | Penalties |

---

### Understat

**Player Seasonal Statistics**

Expected goals (xG) and related advanced metrics per season.

| Column | Description |
|---|---|
| `league`, `season`, `game`, `game_id`, `date` | Match identifiers |
| `team`, `player`, `jersey_number`, `nation`, `pos`, `age`, `min` | Player identifiers |
| `Performance_Gls`, `Performance_Ast`, `Performance_PK`, `Performance_PKatt` | Goal contributions |
| `Performance_Sh`, `Performance_SoT` | Shooting |
| `Performance_CrdY`, `Performance_CrdR` | Disciplinary |
| `Performance_Fls`, `Performance_Fld`, `Performance_Off`, `Performance_Crs` | Defensive & misc |
| `Performance_TklW`, `Performance_Int`, `Performance_OG` | Defending |
| `Performance_PKwon`, `Performance_PKcon` | Penalties |

---

## Transfer / Market Value Data

### TransferMarkt

Player transfer records including fees, market values, and loan movements.

| Column | Description |
|---|---|
| `Season`, `league`, `club`, `window` | Transfer context |
| `movement` | `in` / `out` |
| `player_name`, `player_id`, `age`, `nationality`, `position`, `pos` | Player identifiers |
| `market_value` | Transfermarkt estimated value (€) |
| `dealing_club`, `dealing_country` | Counterparty |
| `fee` | Actual transfer fee (€) — **model target** |
| `is_loan` | Boolean flag for loan moves |

---

## Salary & Contract Data

> ⚠️ **Capology data is not yet under the file naming convention** (freshly scraped). Integration is in progress.

### Capology — Contract Extensions

| Column | Description |
|---|---|
| `league`, `club`, `name`, `name_link` | Identifiers |
| `weekly_gross_{eur,gbp,usd}` / `weekly_net_{eur,gbp,usd}` | Weekly salary |
| `annual_gross_{eur,gbp,usd}` / `annual_net_{eur,gbp,usd}` | Annual salary |
| `bonus_gross_{eur,gbp,usd}` / `bonus_net_{eur,gbp,usd}` | Bonuses |
| `total_gross_*` / `total_net_*` | Total compensation |
| `adjusted_total_gross_*` / `adjusted_total_net_*` | Inflation-adjusted totals |
| `contract_total_gross_*` / `contract_total_net_*` | Full contract value |
| `signed`, `expiration`, `years` | Contract duration |
| `season_link`, `season` | Season reference |

### Capology — Club Finances

| Column | Description |
|---|---|
| `League`, `club` | Identifiers |
| `statement`, `line_order`, `item` | Financial statement line |
| `year`, `closing_date`, `competition` | Temporal context |
| `currency`, `value` | Financial figure |

### Capology — Historical Payrolls

| Column | Description |
|---|---|
| `League`, `club`, `season`, `competition` | Identifiers |
| `currency`, `salary_type` | Currency and gross/net |
| `weekly_fixed`, `annual_fixed`, `bonus` | Wage breakdown |
| `annual_total`, `annual_total_inflation_adjusted` | Total cost |

### Capology — Payroll Distribution

| Column | Description |
|---|---|
| `League`, `club`, `season`, `salary_type` | Identifiers |
| `position`, `position_code` | Position bucket |
| `share_of_payroll_pct` | % of total wage bill |

### Capology — Payroll Highlights

| Column | Description |
|---|---|
| `League`, `club`, `season` | Identifiers |
| `page_title`, `league_name` | Metadata |
| `default_currency`, `currency`, `salary_type` | Currency context |
| `weekly_fixed`, `annual_fixed`, `annual_total` | Wage figures |
| `avg_salary_page`, `avg_total_incl_bonus` | Averages |
| `players_with_salary`, `players_total`, `sum_of_player_salaries` | Squad coverage |
| `matches_page_total` | Match reference |

### Capology — Player Salaries

| Column | Description |
|---|---|
| `League`, `club`, `season`, `player`, `player_id`, `player_url` | Identifiers |
| `verified`, `status`, `active`, `loan` | Data quality flags |
| `position`, `position_detail`, `starter` | Role |
| `age`, `country`, `signed`, `expiration`, `years_remaining` | Profile & contract |
| `annual_gross_{eur,gbp,usd}` / `annual_net_{eur,gbp,usd}` | Annual salary |
| `bonus_gross_*` / `bonus_net_*` | Bonuses |
| `total_gross_*` / `total_net_*` | Total compensation |
| `adjusted_total_gross_*` / `adjusted_total_net_*` | Inflation-adjusted |
| `contract_total_gross_*` / `contract_total_net_*` | Full contract value |
| `release_clause_{eur,gbp,usd}` | Release clause |

---

## Other Datasets

### WorldBank — Economic Inflation

Used to inflation-adjust historical salary and fee figures.

| Column | Description |
|---|---|
| `CountryCode` | ISO 3166-1 alpha-3 country code |
| `Region` | World Bank region |
| `IncomeGroup` | Income classification |
| `SpecialNotes` | WorldBank metadata notes |
| `TableName` | Country name |
| *(year columns)* | Annual inflation rate per country |

---

## `data/` Folder Layout

Large files are **not committed to Git** — they live in MinIO. The local `data/` directory mirrors the MinIO bucket structure and is used for development only.

```
data/
├── raw/                        # Source files as downloaded — one subfolder per league/source
│   ├── eng-premier-league/     # Premier League
│   ├── esp-la-liga/            # La Liga
│   ├── fra-ligue-1/            # Ligue 1
│   ├── ger-bundesliga/         # Bundesliga
│   ├── ita-serie-a/            # Serie A
│   ├── transfermarkt/          # Transfer records (one subfolder per league)
│   │   ├── premier_league/
│   │   ├── laliga/
│   │   ├── ligue_1/
│   │   ├── bundesliga/
│   │   └── serie_a/
│   ├── capology/               # Salary & contract data (one subfolder per league)
│   │   ├── eng-premier-league/
│   │   ├── esp-la-liga/
│   │   ├── fra-ligue-1/
│   │   ├── ger-bundesliga/
│   │   ├── ita-serie-a/
│   │   └── capology_manual/    # Older hand-collected Capology CSVs (pre-scraper)
│   ├── worldbank/
│   │   └── economicinflation_worldbank/
│   └── dataset_lesiones.csv    # Injury history dataset
├── interim/                    # Intermediate transformations (gitignored)
├── processed/                  # Final analytical tables ready for modelling
│   └── df_xvalue.parquet       # Main modelling dataset (gitignored)
└── external/                   # Third-party data not generated by this project
```

### Raw File Naming Pattern

Per-league files follow the convention described above:

```
{league}_{season}_{type}_{source}.csv
```

| Segment | Example values |
|---|---|
| `league` | `eng-premier-league`, `esp-la-liga`, `fra-ligue-1`, `ger-bundesliga`, `ita-serie-a` |
| `season` | `1011`, `2324`, `2526` (last two digits of each year, e.g. `2324` = 2023/24) |
| `type` | `stats`, `matchstats`, `transfers` |
| `source` | `fbref`, `understat`, `transfermarkt` |

### Coverage by Source and League

| Source | Type | Leagues | Seasons |
|---|---|---|---|
| **FBRef** | Seasonal stats | All 5 | 2010/11 → 2025/26 |
| **FBRef** | Match stats | All 5 | 2020/21 → 2024/25 |
| **Understat** | Seasonal stats | All 5 | 2014/15 → 2025/26 |
| **TransferMarkt** | Transfers | All 5 | 1992/93 → 2025/26 |
| **Capology** | Salaries & contracts | All 5 | 2016/17 → 2021/22 (manual) + scraped |
| **WorldBank** | Inflation | Global | Varies by country |
| **Injuries** | Injury history | — | `dataset_lesiones.csv` |
