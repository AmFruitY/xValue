"""
Extracts player name, league, and market value from the joined dataset.

Output: data/processed/player_market_value.csv
"""

import pandas as pd
from pathlib import Path

INPUT_PATH = Path("data/processed/all_players_joined.csv")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    subset = df[["player", "league", "market_value_in_eur"]]

    out_path = OUTPUT_DIR / "player_market_value.csv"
    subset.to_csv(out_path, index=False)

    print(f"Rows: {len(subset)}")
    print(f"Saved to '{out_path}'")


if __name__ == "__main__":
    main()
