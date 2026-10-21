"""
parse_fbref.py
==============

PURPOSE
-------
Turns the four FBref pages saved for a league (Standard, Shooting, Playing
Time, Miscellaneous) into ONE CSV with one row per player per club, using the
same 55 columns as the existing soccerdata files, plus player_id and team_id.

INPUT (made by download_fbref.py):
    data/raw/html/eng-premier-league/eng-premier-league_2627_standard.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_shooting.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_playing_time.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_misc.html

OUTPUT (two copies of the same CSV):
    data/raw/eng-premier-league/eng-premier-league_2627_stats_fbref.csv
        the latest version, replaced every week
    data/raw/snapshots/eng-premier-league/2026-10-20_eng-premier-league_2627_stats_fbref.csv
        a dated copy (date = when the pages were downloaded), kept forever,
        so the weekly history builds up

HOW TO RUN (from the repository's top folder)
----------
    python scraping/fbref/parse_fbref.py                      (every league found)
    python scraping/fbref/parse_fbref.py eng-premier-league   (just one)
    python scraping/fbref/parse_fbref.py eng-premier-league esp-la-liga

Optional:
    --season 2526     parse another season's files (default: the current season)
    --html-dir PATH   where the HTML files are (default: data/raw/html)
    --out-dir PATH    where the latest CSVs go (default: data/raw)
    --snapshot-dir PATH  where the dated copies go (default: data/raw/snapshots)

Requirements:  python -m pip install beautifulsoup4 pandas

HOW IT WORKS (in simple terms)
------------------------------
For each page:
  1. BeautifulSoup turns the HTML into a searchable tree.
  2. The heading ("2026-2027 Premier League Shooting Stats") tells us the
     season and league; we check they match the file name.
  3. In the player table every cell has a `data-stat` label (e.g. "shots").
     We read cells by label, never by position, so a column moving around on
     FBref can't silently shift our data.
Then:
  4. The Standard page gives the list of players (only players who have
     played; the Playing Time page also lists unused substitutes with 0
     matches, and those are left out, as in the soccerdata files).
  5. The other pages' columns are attached to each player by matching
     player ID + club ID (a "left join").
  6. Numbers are cleaned, quality checks run, and the CSV is written.

The function parse_league() can be imported and called from Airflow later.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------

# league folder name -> (name in the page heading, name in the CSV, number of clubs)
LEAGUES = {
    "eng-premier-league": ("Premier League", "ENG-Premier League", 20),
    "esp-la-liga":        ("La Liga",        "ESP-La Liga",        20),
    "fra-ligue-1":        ("Ligue 1",        "FRA-Ligue 1",        18),
    "ger-bundesliga":     ("Bundesliga",     "GER-Bundesliga",     18),
    "ita-serie-a":        ("Serie A",        "ITA-Serie A",        20),
}

# page -> (table id in the HTML, end of the page heading)
PAGES = {
    "standard":     ("stats_standard",     "Stats"),
    "shooting":     ("stats_shooting",     "Shooting Stats"),
    "playing_time": ("stats_playing_time", "Playing Time"),
    "misc":         ("stats_misc",         "Miscellaneous Stats"),
}

# The repository's top folder: this file is in scraping/fbref/, two levels down.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HTML_DIR = REPO_ROOT / "data" / "raw" / "html"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "raw" / "current_season"
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "data" / "raw" / "snapshots"

# The output columns, IN ORDER: (page, FBref data-stat label, CSV column name).
# The CSV names copy FBref's visible headers, like the soccerdata files.
# Note that "Gls", "Ast", "G+A" and "G-PK" appear twice on purpose: first the
# totals, then the per-90-minutes values (pandas reads the second ones as
# "Gls.1", "Ast.1", ...).
OUTPUT_COLUMNS = [
    # identity (taken from the Standard page)
    ("standard", "team",                     "team"),
    ("standard", "player",                   "player"),
    ("standard", "nationality",              "nation"),
    ("standard", "position",                 "pos"),
    ("standard", "age",                      "age"),
    ("standard", "birth_year",               "born"),
    # Standard Stats
    ("standard", "games",                    "MP"),
    ("standard", "games_starts",             "Starts"),
    ("standard", "minutes",                  "Min"),
    ("standard", "minutes_90s",              "90s"),
    ("standard", "goals",                    "Gls"),
    ("standard", "assists",                  "Ast"),
    ("standard", "goals_assists",            "G+A"),
    ("standard", "goals_pens",               "G-PK"),
    ("standard", "pens_made",                "PK"),
    ("standard", "pens_att",                 "PKatt"),
    ("standard", "cards_yellow",             "CrdY"),
    ("standard", "cards_red",                "CrdR"),
    ("standard", "goals_per90",              "Gls"),
    ("standard", "assists_per90",            "Ast"),
    ("standard", "goals_assists_per90",      "G+A"),
    ("standard", "goals_pens_per90",         "G-PK"),
    ("standard", "goals_assists_pens_per90", "G+A-PK"),
    # Shooting
    ("shooting", "shots",                    "Sh"),
    ("shooting", "shots_on_target",          "SoT"),
    ("shooting", "shots_on_target_pct",      "SoT%"),
    ("shooting", "shots_per90",              "Sh/90"),
    ("shooting", "shots_on_target_per90",    "SoT/90"),
    ("shooting", "goals_per_shot",           "G/Sh"),
    ("shooting", "goals_per_shot_on_target", "G/SoT"),
    # Playing Time
    ("playing_time", "minutes_per_game",     "Mn/MP"),
    ("playing_time", "minutes_pct",          "Min%"),
    ("playing_time", "minutes_per_start",    "Mn/Start"),
    ("playing_time", "games_complete",       "Compl"),
    ("playing_time", "games_subs",           "Subs"),
    ("playing_time", "minutes_per_sub",      "Mn/Sub"),
    ("playing_time", "unused_subs",          "unSub"),
    ("playing_time", "points_per_game",      "PPM"),
    ("playing_time", "on_goals_for",         "onG"),
    ("playing_time", "on_goals_against",     "onGA"),
    ("playing_time", "plus_minus",           "+/-"),
    ("playing_time", "plus_minus_per90",     "+/-90"),
    ("playing_time", "plus_minus_wowy",      "On-Off"),
    # Miscellaneous
    ("misc", "cards_yellow_red",             "2CrdY"),
    ("misc", "fouls",                        "Fls"),
    ("misc", "fouled",                       "Fld"),
    ("misc", "offsides",                     "Off"),
    ("misc", "crosses",                      "Crs"),
    ("misc", "interceptions",                "Int"),
    ("misc", "tackles_won",                  "TklW"),
    ("misc", "pens_won",                     "PKwon"),   # empty since Jan 2026
    ("misc", "pens_conceded",                "PKcon"),   # empty since Jan 2026
    ("misc", "own_goals",                    "OG"),
]

# Labels that are text, not numbers.
TEXT_LABELS = {"team", "player", "nationality", "position", "age"}

# Labels holding decimals; every other numeric label is a whole number.
DECIMAL_LABELS = {
    "minutes_90s", "goals_per90", "assists_per90", "goals_assists_per90",
    "goals_pens_per90", "goals_assists_pens_per90", "shots_on_target_pct",
    "shots_per90", "shots_on_target_per90", "goals_per_shot",
    "goals_per_shot_on_target", "minutes_pct", "points_per_game",
    "plus_minus_per90", "plus_minus_wowy",
}

# Columns that appear on several pages: used to check the pages agree.
# (page, label on that page, label on the Standard page)
CROSS_CHECKS = [
    ("shooting",     "goals",        "goals"),
    ("playing_time", "games",        "games"),
    ("playing_time", "minutes",      "minutes"),
    ("misc",         "cards_yellow", "cards_yellow"),
]


class ParseError(Exception):
    """Raised when a page isn't what we expect. Airflow will mark the task as
    failed, which is what we want: better no data than wrong data."""


# ---------------------------------------------------------------------------
# 2. HELPERS
# ---------------------------------------------------------------------------

def season_code(on_date):
    """European seasons run August-May. From July onwards we're in the season
    starting this year. e.g. 2026-10-21 -> "2627"; 2027-03-01 -> "2627"."""
    start = on_date.year if on_date.month >= 7 else on_date.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def heading_to_code(season_text):
    """"2026-2027" (as written in the page heading) -> "2627"."""
    return season_text[2:4] + season_text[7:9]


def id_from_link(cell, kind):
    """FBref links look like /en/players/5bc43860/Brenden-Aaronson.
    The 8-character code is FBref's permanent ID, which never changes even if
    a name is spelled differently."""
    link = cell.find("a", href=True) if cell else None
    if link:
        match = re.search(rf"/{kind}/([0-9a-f]{{8}})/", link["href"])
        if match:
            return match.group(1)
    return None


def read_page(html_path, page, league, season):
    """Read one saved page. Returns a DataFrame with one column per data-stat
    label (all as text), plus player_id and team_id."""
    table_id, heading_end = PAGES[page]
    heading_league = LEAGUES[league][0]
    soup = BeautifulSoup(Path(html_path).read_text(encoding="utf-8"), "html.parser")

    # --- Heading, e.g. "2026-2027 Premier League Shooting Stats"
    heading = soup.find("h1")
    heading_text = " ".join(heading.get_text().split()) if heading else ""
    heading_text = heading_text.replace("(M) ", "")   # e.g. "Serie A (M)"
    match = re.fullmatch(rf"(\d{{4}}-\d{{4}}) (.+) {heading_end}", heading_text)
    if not match:
        raise ParseError(f"{html_path.name}: unexpected heading '{heading_text}'")
    season_text, found_league = match.groups()
    if found_league != heading_league:
        raise ParseError(f"{html_path.name}: page is for '{found_league}', "
                         f"expected '{heading_league}'")
    # The download script named the file after the season it expected. If
    # the page shows another season (e.g. FBref hadn't switched to the new
    # season yet in July), the data would be mislabelled, so we stop.
    if heading_to_code(season_text) != season:
        raise ParseError(f"{html_path.name}: page shows season {season_text}, "
                         f"but the file name says {season}")

    # --- The table. The page also holds a hidden copy inside an HTML comment;
    # BeautifulSoup ignores comments, so this finds the visible one.
    table = soup.find("table", id=table_id)
    if table is None:
        raise ParseError(f"{html_path.name}: table '{table_id}' not found")

    labels = {th.get("data-stat") for th in table.find("thead").find_all("th")}
    needed = {label for p, label, _ in OUTPUT_COLUMNS if p == page}
    needed |= {label for p, label, _ in CROSS_CHECKS if p == page}
    missing = needed - labels
    if missing:
        raise ParseError(f"{html_path.name}: columns missing: {sorted(missing)}")

    # --- Rows
    records = []
    for row in table.find("tbody").find_all("tr"):
        if "thead" in (row.get("class") or []):   # repeated header rows
            continue
        cells = {c.get("data-stat"): c for c in row.find_all(["th", "td"])}
        # get_text(" ", ...) keeps a space between pieces of text, so the
        # flag's hidden "us" and the code "USA" stay separate ("us USA").
        record = {label: cell.get_text(" ", strip=True) for label, cell in cells.items()}
        record["player_id"] = id_from_link(cells.get("player"), "players")
        record["team_id"] = id_from_link(cells.get("team"), "squads")
        records.append(record)

    if not records:
        raise ParseError(f"{html_path.name}: the table has no player rows")
    return pd.DataFrame(records)


def to_number(text_column, decimal):
    """'1,234' -> 1234 ; '+12' -> 12 ; '' -> blank."""
    cleaned = text_column.str.replace(",", "", regex=False).str.replace("+", "", regex=False)
    numbers = pd.to_numeric(cleaned, errors="coerce")
    # "Int64" (capital I) = whole numbers that may contain blanks.
    return numbers if decimal else numbers.astype("Int64")


# ---------------------------------------------------------------------------
# 3. PARSING ONE LEAGUE (4 pages -> 1 table)
# ---------------------------------------------------------------------------

def parse_league(html_dir, league, season):
    """Parse the four pages of one league and season. Returns the final DataFrame."""
    league_folder = Path(html_dir) / league
    _, csv_league, expected_clubs = LEAGUES[league]

    pages = {}
    for page in PAGES:
        path = league_folder / f"{league}_{season}_{page}.html"
        if not path.exists():
            raise ParseError(f"missing file {path}")
        pages[page] = read_page(path, page, league, season)

    key = ["player_id", "team_id"]
    for page, df in pages.items():
        if df[key].isna().any().any():
            raise ParseError(f"{page} page: some rows have no player or club ID")
        if df.duplicated(key).any():
            raise ParseError(f"{page} page: duplicated player+club rows")

    # Start from the Standard page (only players who have played) and attach
    # the other pages' columns. Each page's columns get a prefix such as
    # "shooting:" so that labels shared by several pages (e.g. "goals") don't clash.
    merged = pages["standard"].add_prefix("standard:").rename(
        columns={"standard:player_id": "player_id", "standard:team_id": "team_id"})
    for page in ["shooting", "playing_time", "misc"]:
        other = pages[page].add_prefix(f"{page}:").rename(
            columns={f"{page}:player_id": "player_id", f"{page}:team_id": "team_id"})
        merged = merged.merge(other, on=key, how="left", indicator=True)
        not_found = (merged["_merge"] == "left_only").sum()
        if not_found:
            raise ParseError(f"{not_found} players from the Standard page are "
                             f"missing on the {page} page")
        merged = merged.drop(columns="_merge")

    # Pages must agree where they show the same number. If they don't, the
    # pages are from different moments (e.g. one page failed to download and
    # an older week's file is still there) or rows were matched wrongly.
    for page, label, standard_label in CROSS_CHECKS:
        a = to_number(merged[f"{page}:{label}"], decimal=False)
        b = to_number(merged[f"standard:{standard_label}"], decimal=False)
        differences = (a.fillna(-1) != b.fillna(-1)).sum()
        if differences:
            raise ParseError(f"'{label}' differs between the {page} and standard "
                             f"pages for {differences} players (pages from "
                             f"different downloads?)")

    # --- Build the output table, column by column, in the right order.
    out = pd.DataFrame(index=merged.index)
    out["league"] = csv_league
    out["season"] = season
    for page, label, _ in OUTPUT_COLUMNS:
        values = merged[f"{page}:{label}"]
        if label == "nationality":
            values = values.str.split().str[-1]           # "us USA" -> "USA"
        elif label == "age":
            values = to_number(values.str.split("-").str[0], decimal=False)  # "25-363" -> 25
        elif label not in TEXT_LABELS:
            values = to_number(values, decimal=label in DECIMAL_LABELS)
        out[f"{page}:{label}"] = values
    out["player_id"] = merged["player_id"]
    out["team_id"] = merged["team_id"]

    # Youngest first, like the soccerdata files.
    out = out.sort_values(["standard:age", "standard:team", "standard:player"],
                          kind="stable").reset_index(drop=True)

    check_quality(out, expected_clubs)

    # Final column names (with the repeated "Gls", "Ast", ... names).
    out.columns = (["league", "season"] + [name for _, _, name in OUTPUT_COLUMNS]
                   + ["player_id", "team_id"])
    return out


# ---------------------------------------------------------------------------
# 4. QUALITY CHECKS
# ---------------------------------------------------------------------------

def check_quality(df, expected_clubs):
    problems = []
    n_clubs = df["standard:team"].nunique()
    if n_clubs != expected_clubs:
        problems.append(f"{n_clubs} clubs found, expected {expected_clubs}")
    if (df["standard:games_starts"] > df["standard:games"]).any():
        problems.append("more starts than matches played")
    if (df["standard:games"] > 38).any():
        problems.append("more than 38 matches played")
    if (df["shooting:shots_on_target"] > df["shooting:shots"]).any():
        problems.append("more shots on target than shots")
    if (df["standard:goals"] + df["standard:assists"] != df["standard:goals_assists"]).any():
        problems.append("goals + assists does not equal G+A")
    if problems:
        raise ParseError("quality checks failed: " + "; ".join(problems))


# ---------------------------------------------------------------------------
# 5. SAVING
# ---------------------------------------------------------------------------

def download_date(html_dir, league, season):
    """The day the Standard page was saved by download_fbref.py, taken from
    the file's "last modified" time (in the computer's local time zone)."""
    path = Path(html_dir) / league / f"{league}_{season}_standard.html"
    return date.fromtimestamp(path.stat().st_mtime)


def write_csv(df, path):
    """Write to a temporary file first, then rename: an existing CSV is only
    replaced once the new one is completely written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)
    return path


# ---------------------------------------------------------------------------
# 6. COMMAND LINE
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Parse saved FBref pages into CSVs.")
    parser.add_argument("leagues", nargs="*",
                        help="leagues to parse (default: every league with files): "
                             + ", ".join(LEAGUES))
    parser.add_argument("--season", default=season_code(date.today()),
                        help="season code, e.g. 2627 (default: current season)")
    parser.add_argument("--html-dir", default=str(DEFAULT_HTML_DIR),
                        help="folder with the league HTML folders")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                        help="base folder for the latest CSVs")
    parser.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR),
                        help="base folder for the dated weekly copies")
    args = parser.parse_args()

    html_dir, out_dir, season = Path(args.html_dir), Path(args.out_dir), args.season
    snapshot_dir = Path(args.snapshot_dir)

    unknown = [lg for lg in args.leagues if lg not in LEAGUES]
    if unknown:
        parser.error(f"unknown league(s): {', '.join(unknown)}. "
                     f"Choose from: {', '.join(LEAGUES)}")
    if not re.fullmatch(r"\d{4}", season):
        parser.error(f"--season must look like 2627, not '{season}'")

    # Which leagues? Those asked for, or every league whose files exist.
    leagues = args.leagues or [
        lg for lg in LEAGUES
        if (html_dir / lg / f"{lg}_{season}_standard.html").exists()
    ]
    if not leagues:
        print(f"No season-{season} HTML files found in {html_dir}")
        sys.exit(1)

    failed = []
    for league in leagues:
        print(f"\n{league} {season}:")
        try:
            df = parse_league(html_dir, league, season)
        except ParseError as error:
            print(f"   FAILED: {error}")
            failed.append(league)
            continue

        file_name = f"{league}_{season}_stats_fbref.csv"
        print(f"   {len(df)} rows, {df['team'].nunique()} clubs, "
              f"{df['player_id'].nunique()} players, {df.shape[1]} columns")

        # 1) The latest version, replaced every week.
        latest = write_csv(df, out_dir / league / file_name)
        print(f"   Latest:   {latest}")

        # 2) A dated copy that is never replaced by later weeks, so the
        # weekly history builds up. The date is when the pages were
        # downloaded (the save time of the Standard HTML file).
        downloaded_on = download_date(html_dir, league, season)
        snapshot = write_csv(
            df, snapshot_dir / league / f"{downloaded_on.isoformat()}_{file_name}")
        print(f"   Snapshot: {snapshot}")

    if failed:
        print(f"\nFAILED leagues: {', '.join(failed)}")
        sys.exit(1)   # non-zero exit = Airflow marks the task as failed


if __name__ == "__main__":
    main()