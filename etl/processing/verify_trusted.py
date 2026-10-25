"""
verify_trusted.py
=================
Checks that the data in the Trusted Zone is CORRECT, not just tidy.
It automates the manual validation in our data validation report
(Stage 1: season integrity, Stage 2: comparison with reference sources).

Run it after clean_to_trusted.py (in Airflow: the next task):

    python verify_trusted.py                      # all seasons
    python verify_trusted.py --seasons current    # only this season (weekly)

Every check prints PASS, WARN or FAIL. Any FAIL -> exit code 1 -> the
Airflow task turns red, so nobody trains a model on wrong data.

-----------------------------------------------------------------------
THE SEVEN CHECKS
-----------------------------------------------------------------------
 1. coverage        no season is missing between a league's first and last season
 2. complete season every finished season has a player with close to a full
                    season of matches (>= 30 of 38, >= 28 of 34)
 3. clubs           clubs that MUST be in a season (promoted) are there, clubs that
                    must NOT be (relegated) are not         <- reference_checks.csv
 4. known values    known season totals match, e.g. Haaland's goals
                                                            <- reference_checks.csv
 5. cross-source    FBref and Understat agree on goals and assists for the same
                    player and season (within +-1 for at least 95% of players)
 6. match stats     every match of a finished season is present (380 or 306)
 7. match vs season a player's goals/assists added up over his matches equal his
                    season totals (same source: exact for at least 95% of players)

 Checks 3 and 4 read reference_checks.csv. Add a row every time you verify
 something by hand: from then on it is checked automatically, every week.

-----------------------------------------------------------------------
SETTINGS (environment variables, same as clean_to_trusted.py)
-----------------------------------------------------------------------
    TRUSTED_ROOT       default s3a://xvalue-data/trusted_zone (or a local folder)
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY   (only for MinIO)
    REFERENCE_FILE     default reference_checks.csv next to this script
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from datetime import date

import duckdb

# Column names per table (as written by clean_to_trusted.py).
TABLES = {
    "fbref": dict(table="fbref_player_stats", matches="MP", goals="Gls", assists="Ast"),
    "understat": dict(table="understat_player_stats", matches="matches",
                      goals="goals", assists="assists"),
}
MIN_FULL_SEASON = {38: 30, 34: 28}   # matchdays -> matches a regular player must reach
# Seasons that really were shorter. (league, season start) -> matches needed.
SHORT_SEASONS = {
    ("fra-ligue-1", 2019): 24,       # 2019-20 stopped after 28 matchdays (COVID)
}
CROSS_SOURCE_LIMIT = 0.95            # share of players that must agree within +-1
CROSS_SOURCE_MIN_PLAYERS = 20        # don't judge a season on fewer matched players

results = []                         # (status, check, detail)


def record(status, check, detail):
    results.append((status, check, detail))
    print(f"  {status:<4}  {check:<15} {detail}")


def key_text(text):
    """Same rule as player_key/team_key in the cleaning script."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def current_season_start(today=None):
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def matchdays(league, start):
    if league == "ger-bundesliga":
        return 34
    if league == "fra-ligue-1" and (start >= 2023 or start <= 2001):
        return 34
    if league == "ita-serie-a" and start <= 2003:
        return 34
    return 38


# ---------------------------------------------------------------------
# Reading the Trusted Zone
# ---------------------------------------------------------------------

def connect(root):
    con = duckdb.connect()
    if root.startswith("s3a://") or root.startswith("s3://"):
        endpoint = os.environ["MINIO_ENDPOINT"]
        con.sql("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"""CREATE SECRET minio (TYPE s3,
            KEY_ID '{os.environ["MINIO_ACCESS_KEY"]}', SECRET '{os.environ["MINIO_SECRET_KEY"]}',
            ENDPOINT '{re.sub(r"^https?://", "", endpoint)}', URL_STYLE 'path',
            USE_SSL {str(endpoint.startswith("https")).lower()})""")
        root = "s3://" + root.split("://", 1)[1]
    return con, root.rstrip("/")


def exists(con, root, table):
    try:
        con.sql(f"SELECT 1 FROM read_parquet('{root}/{table}/**/*.parquet') LIMIT 1").fetchall()
        return True
    except duckdb.Error:
        return False


def source(root, table, starts):
    """SQL for one Trusted table, limited to the chosen seasons."""
    sql = (f"(SELECT * FROM read_parquet('{root}/{table}/**/*.parquet', "
           f"hive_partitioning = true, union_by_name = true)")
    if starts:
        sql += f" WHERE season_start IN ({', '.join(map(str, starts))})"
    return sql + ")"


# ---------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------

def check_coverage(con, root, starts):
    for table in ("fbref_player_stats", "fbref_player_match_stats", "understat_player_stats", "transfers"):
        if not exists(con, root, table):
            record("WARN", "coverage", f"{table}: table not found")
            continue
        rows = con.sql(f"""SELECT league, list(DISTINCT season_start ORDER BY season_start)
                           FROM {source(root, table, None)} GROUP BY league ORDER BY league""").fetchall()
        for league, seasons in rows:
            gaps = sorted(set(range(seasons[0], seasons[-1] + 1)) - set(seasons))
            if starts and table == "fbref_player_stats" and not all(s in seasons for s in starts):
                # FBref is the weekly source: this season must be there.
                record("FAIL", "coverage", f"{table} {league}: chosen season(s) missing")
            elif gaps:
                record("FAIL", "coverage", f"{table} {league}: missing seasons "
                       f"{[f'{g}-{(g + 1) % 100:02d}' for g in gaps]}")
            else:
                record("PASS", "coverage", f"{table} {league}: {seasons[0]}-{seasons[-1] + 1} "
                       f"({len(seasons)} seasons, none missing)")


def check_complete_seasons(con, root, starts):
    current = current_season_start()
    for name, cfg in TABLES.items():
        if not exists(con, root, cfg["table"]):
            continue
        rows = con.sql(f"""SELECT league, season, season_start, max("{cfg['matches']}")
                           FROM {source(root, cfg['table'], starts)}
                           GROUP BY ALL ORDER BY league, season_start""").fetchall()
        bad = []
        for league, season, start, top in rows:
            if start >= current:
                continue                                  # season still being played
            need = SHORT_SEASONS.get((league, start), MIN_FULL_SEASON[matchdays(league, start)])
            if (top or 0) < need:
                bad.append(f"{league} {season} (max {top:g}, need {need})")
        finished = sum(1 for r in rows if r[2] < current)
        if bad:
            record("FAIL", "complete season", f"{name}: {len(bad)} incomplete: {'; '.join(bad[:5])}")
        elif finished:
            record("PASS", "complete season", f"{name}: {finished} finished seasons all complete")


def load_reference(path):
    if not os.path.exists(path):
        record("WARN", "reference", f"{path} not found: checks 3 and 4 skipped")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("check") and not r["check"].startswith("#")]


def check_reference(con, root, rows, starts):
    for r in rows:
        start = int(r["season"][:4])
        if starts and start not in starts:
            continue
        cfg = TABLES[r.get("table") or "fbref"]
        if not exists(con, root, cfg["table"]):
            record("WARN", "reference", f"{cfg['table']} not found")
            continue
        src = source(root, cfg["table"], [start])
        where = f"league = '{r['league']}'"
        label = f"{r['league']} {r['season']}"

        if r["check"] in ("club_present", "club_absent"):
            n = con.execute(f"SELECT count(*) FROM {src} WHERE {where} AND team_key = ?",
                            [key_text(r["club"])]).fetchall()[0][0]
            ok = n > 0 if r["check"] == "club_present" else n == 0
            word = "present" if r["check"] == "club_present" else "absent"
            record("PASS" if ok else "FAIL", "clubs",
                   f"{label}: {r['club']} should be {word}" + ("" if ok else f" ({n} rows found)"))

        elif r["check"] == "player_value":
            column = r["column"]
            value, n = con.execute(
                f'SELECT sum("{column}"), count(*) FROM {src} WHERE {where} AND player_key = ?',
                [key_text(r["player"])]).fetchall()[0]
            expected, tol = float(r["expected"]), float(r.get("tolerance") or 0)
            text = f"{label}: {r['player']} {column} = {value if value is None else f'{value:g}'}" \
                   f" (expected {expected:g}{f' +-{tol:g}' if tol else ''}, {cfg['table']})"
            if n == 0:
                record("FAIL", "known values", f"{label}: {r['player']} not found in {cfg['table']}")
            else:
                record("PASS" if value is not None and abs(value - expected) <= tol else "FAIL",
                       "known values", text)
        else:
            record("WARN", "reference", f"unknown check type '{r['check']}'")


def check_cross_source(con, root, starts):
    f, u = TABLES["fbref"], TABLES["understat"]
    if not (exists(con, root, f["table"]) and exists(con, root, u["table"])):
        record("WARN", "cross-source", "needs both FBref and Understat tables")
        return
    # FBref has one row per player per CLUB: add them up per player first.
    rows = con.sql(f"""
        WITH fb AS (SELECT league, season, season_start, player_key,
                           sum("{f['goals']}") g, sum("{f['assists']}") a
                    FROM {source(root, f['table'], starts)} GROUP BY ALL),
             us AS (SELECT league, season, player_key,
                           sum("{u['goals']}") g, sum("{u['assists']}") a
                    FROM {source(root, u['table'], starts)} GROUP BY ALL),
             both_ AS (SELECT fb.league, fb.season, fb.season_start,
                              abs(fb.g - us.g) <= 1 AS goals_ok, abs(fb.a - us.a) <= 1 AS assists_ok
                       FROM fb JOIN us USING (league, season, player_key))
        SELECT b.league, b.season, count(*) matched,
               avg(goals_ok::INT) goals_share, avg(assists_ok::INT) assists_share,
               (SELECT count(*) FROM fb WHERE fb.league = b.league AND fb.season = b.season) fb_players
        FROM both_ b GROUP BY ALL ORDER BY b.league, any_value(b.season_start)""").fetchall()
    if not rows:
        record("WARN", "cross-source", "no season present in both FBref and Understat")
    for league, season, matched, goals, assists, total in rows:
        text = (f"{league} {season}: {matched}/{total} FBref players matched by name; "
                f"goals within +-1 {goals:.0%}, assists {assists:.0%}")
        if matched < CROSS_SOURCE_MIN_PLAYERS:
            record("WARN", "cross-source", text + " (too few matches to judge)")
        elif min(goals, assists) < CROSS_SOURCE_LIMIT:
            record("FAIL", "cross-source", text)
        else:
            record("PASS", "cross-source", text)


def check_match_stats(con, root, starts):
    """6. Every match of a finished season is there (380 or 306), and
    7. a player's goals and assists added up over his matches equal his
       season totals in fbref_player_stats (same source, so nearly exact)."""
    m = "fbref_player_match_stats"
    if not exists(con, root, m):
        record("WARN", "match stats", f"{m}: table not found")
        return
    current = current_season_start()
    # League matches only: play-offs (is_playoff) are extra matches by design.
    rows = con.sql(f"""SELECT league, season, season_start, count(DISTINCT game_id)
                       FROM {source(root, m, starts)} WHERE NOT coalesce(is_playoff, false)
                       GROUP BY ALL ORDER BY league, season_start""").fetchall()
    bad, finished = [], 0
    for league, season, start, games in rows:
        if start >= current:
            continue
        finished += 1
        clubs = 18 if matchdays(league, start) == 34 else 20
        if games != clubs * (clubs - 1):
            bad.append(f"{league} {season} ({games} of {clubs * (clubs - 1)})")
    if bad:
        record("FAIL", "match stats", f"{len(bad)} seasons with missing matches: {'; '.join(bad[:5])}")
    elif finished:
        record("PASS", "match stats", f"{finished} finished seasons have every match")

    if not exists(con, root, "fbref_player_stats"):
        return
    rows = con.sql(f"""
        WITH m AS (SELECT league, season, season_start, player_key, team_key,
                          sum("Performance_Gls") g, sum("Performance_Ast") a
                   FROM {source(root, m, starts)} WHERE NOT coalesce(is_playoff, false) GROUP BY ALL),
             s AS (SELECT league, season, player_key, team_key, sum("Gls") g, sum("Ast") a
                   FROM {source(root, 'fbref_player_stats', starts)} GROUP BY ALL)
        SELECT m.league, m.season, count(*) n,
               avg((m.g = s.g)::INT) goals_exact, avg((m.a = s.a)::INT) assists_exact
        FROM m JOIN s USING (league, season, player_key, team_key)
        GROUP BY ALL ORDER BY m.league, any_value(m.season_start)""").fetchall()
    for league, season, n, goals, assists in rows:
        text = (f"{league} {season}: {n} players; match sums equal season totals for "
                f"goals {goals:.0%}, assists {assists:.0%}")
        record("PASS" if min(goals, assists) >= CROSS_SOURCE_LIMIT else "FAIL", "match vs season", text)


# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify the Trusted Zone")
    parser.add_argument("--seasons", default="all",
                        help="'all' (default), 'current' or a list like 2025-26,2026-27")
    args = parser.parse_args()
    starts = (None if args.seasons == "all"
              else [current_season_start()] if args.seasons == "current"
              else [int(s[:4]) for s in args.seasons.split(",")])

    con, root = connect(os.environ.get("TRUSTED_ROOT", "s3a://xvalue-data/trusted_zone"))
    reference = os.environ.get("REFERENCE_FILE", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "reference_checks.csv"))
    print(f"Verifying {root} | seasons: {args.seasons}\n")

    check_coverage(con, root, starts)
    check_complete_seasons(con, root, starts)
    check_reference(con, root, load_reference(reference), starts)
    check_cross_source(con, root, starts)
    check_match_stats(con, root, starts)

    count = {s: sum(1 for r in results if r[0] == s) for s in ("PASS", "WARN", "FAIL")}
    print(f"\n{count['PASS']} passed, {count['WARN']} warnings, {count['FAIL']} failed")
    sys.exit(1 if count["FAIL"] else 0)


if __name__ == "__main__":
    main()