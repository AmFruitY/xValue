"""
Downloads FBref player season stats for the top 5 European leagues across
seasons 2018/19 – 2022/23, for players of all ages.

Output: data/all_players.csv
"""

import pandas as pd
import soccerdata as sd
from pathlib import Path

from etl.minio_client import upload_file

LEAGUES = ["Big 5 European Leagues Combined"]

# soccerdata season format: last two digits of each year concatenated
SEASONS = ["1819", "1920", "2021", "2122", "2223"]

# Stat types available: standard, keeper, shooting, playing_time, misc
STAT_TYPES = ["standard", "shooting", "playing_time", "misc"]

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(exist_ok=True)


def fetch_stat(fbref: sd.FBref, stat_type: str) -> pd.DataFrame:
    print(f"  Fetching '{stat_type}' stats...")
    df = fbref.read_player_season_stats(stat_type=stat_type)
    # Flatten MultiIndex columns: take the last non-empty level
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            next((col for col in reversed(col_tuple) if col.strip()), col_tuple[-1])
            for col_tuple in df.columns
        ]
    return df


def main() -> None:
    print(f"Initialising FBref scraper for {len(LEAGUES)} leagues, {len(SEASONS)} seasons...")
    fbref = sd.FBref(leagues=LEAGUES, seasons=SEASONS)

    # Fetch all stat types and find which has Age
    all_dfs = {}
    for stat_type in STAT_TYPES:
        df = fetch_stat(fbref, stat_type)
        df = df.reset_index()
        all_dfs[stat_type] = df
        print(f"  {stat_type}: {list(df.columns)}")

    # Start with standard stats (all have 'age')
    base = all_dfs["standard"].copy()

    # age may be stored as "23-150" (years-days) on FBref – keep only the year part
    base["age"] = (
        base["age"]
        .astype(str)
        .str.split("-")
        .str[0]
    )
    base["age"] = pd.to_numeric(base["age"], errors="coerce")
    print(f"\nFound 'age' column in 'standard' stats")

    # Identify the join key columns
    key_cols = [c for c in ["league", "season", "team", "player"] if c in base.columns]
    print(f"Join keys: {key_cols}")

    merged = base.copy()

    # Merge other stat types
    for stat_type, extra in all_dfs.items():
        if stat_type == "standard":
            continue
        # Drop columns already present in merged to avoid duplicates (keep keys + new cols)
        drop_cols = [c for c in extra.columns if c in merged.columns and c not in key_cols]
        extra = extra.drop(columns=drop_cols, errors="ignore")
        merged = merged.merge(extra, on=key_cols, how="left")

    # Keep players of all ages
    all_players = merged.sort_values(["season", "league", "age"])

    out_path = OUTPUT_DIR / "all_players.csv"
    all_players.to_csv(out_path, index=False)

    print(f"\nDone. {len(all_players)} player-season rows saved to '{out_path}'.")
    if "player" in all_players.columns:
        print(all_players[["season", "league", "player", "age"]].head(10).to_string(index=False))

    # Upload to MinIO so the dataset is accessible from any machine
    upload_file(local_path=out_path, object_key="raw/all_players.csv")


if __name__ == "__main__":
    main()
