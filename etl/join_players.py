"""
Joins all_players.csv (FBref player-season stats) with players.csv
(Transfermarkt player bios/market values) on player name.

Name alone is ambiguous (938 duplicate names in players.csv), so the
join also matches on birth year, derived from date_of_birth, to
disambiguate players who share a name.

Output: data/processed/all_players_joined.csv
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    all_players = pd.read_csv(RAW_DIR / "all_players.csv")
    players = pd.read_csv(RAW_DIR / "players.csv")

    players["birth_year"] = pd.to_datetime(
        players["date_of_birth"], errors="coerce"
    ).dt.year

    merged = all_players.merge(
        players,
        left_on=["player", "born"],
        right_on=["name", "birth_year"],
        how="left",
        suffixes=("", "_players"),
    )

    out_path = OUTPUT_DIR / "all_players_joined.csv"
    merged.to_csv(out_path, index=False)

    matched = merged["name"].notna().sum()
    print(f"all_players.csv rows: {len(all_players)}")
    print(f"Joined rows: {len(merged)} ({matched} matched to a player in players.csv)")
    print(f"Saved to '{out_path}'")


if __name__ == "__main__":
    main()
