"""
Downloads StatsBomb OPEN DATA player stats, built from raw match events,
for whichever competitions/seasons are actually free (see COMPETITIONS
below -- this is NOT the same coverage as the FBref version: StatsBomb's
free data does not include full top-5-league seasons for 2018/19-2022/23).

IMPORTANT DIFFERENCE FROM THE FBREF VERSION:
FBref gives you pre-built season-stats tables. StatsBomb only gives raw
events (one row per pass/shot/etc.). So instead of *downloading* stats,
this script *computes* them by counting up events per player -- this is
what "aggregation" means throughout the script.

Output: data/raw/statsbomb_stats_all_players.csv
"""

import pandas as pd
from pathlib import Path
from statsbombpy import sb

from etl.minio_client import upload_file

# ---------------------------------------------------------------------------
# WHICH FREE COMPETITION/SEASONS TO USE
# ---------------------------------------------------------------------------
# Unlike FBref's "Big 5 leagues, 2018/19-2022/23", StatsBomb's free data
# does not cover that. These are the closest genuinely-free entries that
# overlap that era. Check sb.competitions() yourself if you want to adjust --
# la Liga entries are Barcelona's matches only, not the full league.
COMPETITIONS = [
    ("La Liga", "2018/2019"),
    ("La Liga", "2019/2020"),
    ("La Liga", "2020/2021"),
    ("Ligue 1", "2021/2022"),
    ("Ligue 1", "2022/2023"),
]

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_match_ids(comps_df: pd.DataFrame, competition_name: str, season_name: str) -> list[int]:
    row = comps_df[
        (comps_df["competition_name"] == competition_name)
        & (comps_df["season_name"] == season_name)
    ]
    if row.empty:
        print(f"  WARNING: {competition_name} {season_name} not found in free data, skipping.")
        return []
    comp_id = row.iloc[0]["competition_id"]
    season_id = row.iloc[0]["season_id"]
    matches = sb.matches(competition_id=comp_id, season_id=season_id)
    return matches["match_id"].tolist()


def minutes_played_from_lineups(match_id: int) -> pd.DataFrame:
    """
    Approximates minutes played per player in one match.
    StatsBomb doesn't give a direct 'minutes played' number -- we infer it
    from substitution and red-card events, defaulting to a full 90 minutes
    for anyone who started and wasn't subbed or sent off.
    """
    events = sb.events(match_id=match_id)
    lineup = sb.lineups(match_id=match_id)

    rows = []
    for team, lineup_df in lineup.items():
        for _, player_row in lineup_df.iterrows():
            player = player_row["player_name"]

            sub_off = events[
                (events["type"] == "Substitution") & (events["player"] == player)
            ]
            red_card = events[
                (events["type"] == "Foul Committed")
                & (events["player"] == player)
                & (events["foul_committed_card"].isin(["Red Card", "Second Yellow"]))
            ]

            if not sub_off.empty:
                minutes = sub_off.iloc[0]["minute"]
            elif not red_card.empty:
                minutes = red_card.iloc[0]["minute"]
            else:
                minutes = 90  # approximation: played the full match

            rows.append({"match_id": match_id, "team": team, "player": player, "minutes": minutes})

    return pd.DataFrame(rows)


def aggregate_match_events(match_id: int) -> pd.DataFrame:
    """
    Turns one match's raw events into per-player stat totals --
    this replaces FBref's separate 'standard'/'shooting'/'passing'/'defense'
    downloads with hand-built equivalents from the same event stream.
    """
    events = sb.events(match_id=match_id)
    events = events.dropna(subset=["player"])

    # --- shooting stats (StatsBomb's own xG model is built into shot events) ---
    shots = events[events["type"] == "Shot"]
    shooting = shots.groupby(["team", "player"]).agg(
        shots=("type", "count"),
        goals=("shot_outcome", lambda x: (x == "Goal").sum()),
        xg=("shot_statsbomb_xg", "sum"),
    )

    # --- passing stats ---
    passes = events[events["type"] == "Pass"]
    passing = passes.groupby(["team", "player"]).agg(
        passes_attempted=("type", "count"),
        passes_completed=("pass_outcome", lambda x: x.isna().sum()),  # blank outcome = completed
    )

    # --- defensive stats (StatsBomb's 'Pressure' event is where FBref's
    #     own 'pressures' stat concept originated) ---
    pressures = events[events["type"] == "Pressure"]
    defense = pressures.groupby(["team", "player"]).agg(pressures=("type", "count"))

    tackles = events[
        (events["type"] == "Duel") & (events["duel_type"] == "Tackle")
    ]
    tackle_counts = tackles.groupby(["team", "player"]).agg(tackles=("type", "count"))

    combined = (
        shooting.join(passing, how="outer")
        .join(defense, how="outer")
        .join(tackle_counts, how="outer")
        .fillna(0)
        .reset_index()
    )
    combined["match_id"] = match_id
    return combined


def main() -> None:
    print("Fetching free competitions list...")
    comps_df = sb.competitions()

    all_match_stats = []
    all_minutes = []

    for competition_name, season_name in COMPETITIONS:
        print(f"\n{competition_name} {season_name}:")
        match_ids = get_match_ids(comps_df, competition_name, season_name)
        print(f"  {len(match_ids)} matches found")

        for match_id in match_ids:
            try:
                match_stats = aggregate_match_events(match_id)
                match_stats["competition"] = competition_name
                match_stats["season"] = season_name
                all_match_stats.append(match_stats)

                minutes_df = minutes_played_from_lineups(match_id)
                minutes_df["competition"] = competition_name
                minutes_df["season"] = season_name
                all_minutes.append(minutes_df)
            except Exception as e:
                print(f"  Skipping match {match_id} due to error: {e}")

    if not all_match_stats:
        print("No data collected -- check COMPETITIONS list against sb.competitions().")
        return

    # ---- combine every match into one player-season table ----
    match_level = pd.concat(all_match_stats, ignore_index=True)
    minutes_level = pd.concat(all_minutes, ignore_index=True)

    key_cols = ["competition", "season", "team", "player"]

    season_stats = match_level.groupby(key_cols).agg(
        shots=("shots", "sum"),
        goals=("goals", "sum"),
        xg=("xg", "sum"),
        passes_attempted=("passes_attempted", "sum"),
        passes_completed=("passes_completed", "sum"),
        pressures=("pressures", "sum"),
        tackles=("tackles", "sum"),
    ).reset_index()

    season_minutes = minutes_level.groupby(key_cols).agg(
        minutes=("minutes", "sum")
    ).reset_index()

    all_players = season_stats.merge(season_minutes, on=key_cols, how="left")
    all_players = all_players.sort_values(["season", "competition", "player"])

    out_path = OUTPUT_DIR / "statsbomb_stats_all_players.csv"
    all_players.to_csv(out_path, index=False)

    print(f"\nDone. {len(all_players)} player-season rows saved to '{out_path}'.")
    print(all_players.head(10).to_string(index=False))

    upload_file(local_path=out_path, object_key="raw/statsbomb_stats_all_players.csv")


if __name__ == "__main__":
    main()