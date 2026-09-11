"""
Downloads Understat player season stats for the top 5 European leagues across
seasons 2018/19 – present.

Output: data/raw/understat_stats_all_players.csv
"""

import pandas as pd
import soccerdata as sd
from pathlib import Path

from etl.minio_client import upload_file

LEAGUES = ['ENG-Premier League', 'ESP-La Liga', 'FRA-Ligue 1', 'GER-Bundesliga', 'ITA-Serie A']

# soccerdata season format: last two digits of each year concatenated
# 2018/19 to present (e.g. up to 23/24)
SEASONS = ["1819", "1920", "2021", "2122", "2223", "2324"]

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


def main() -> None:
    print(f"Initialising Understat scraper for {len(LEAGUES)} leagues, {len(SEASONS)} seasons...")
    un = sd.Understat(leagues=LEAGUES, seasons=SEASONS)

    print("  Fetching player season stats...")
    df = un.read_player_season_stats()
    
    # Flatten the dataframe
    df = df.reset_index()

    # The columns returned by Understat typically include:
    # 'league', 'season', 'team', 'player', 'goals', 'xg', 'assists', 'xa', 'shots', etc.
    print(f"\nFetched {len(df)} rows. Columns: {list(df.columns)}")

    # Sort by season, league, and player
    sort_cols = [col for col in ["season", "league", "player"] if col in df.columns]
    if sort_cols:
        all_players = df.sort_values(sort_cols)
    else:
        all_players = df

    out_path = OUTPUT_DIR / "understat_stats_all_players.csv"
    all_players.to_csv(out_path, index=False)

    print(f"\nDone. {len(all_players)} player-season rows saved to '{out_path}'.")
    if "player" in all_players.columns:
        cols_to_print = [c for c in ["season", "league", "player", "goals", "xg"] if c in all_players.columns]
        print(all_players[cols_to_print].head(10).to_string(index=False))

    # Upload to MinIO so the dataset is accessible from any machine
    upload_file(local_path=out_path, object_key="raw/understat_stats_all_players.csv")


if __name__ == "__main__":
    main()
