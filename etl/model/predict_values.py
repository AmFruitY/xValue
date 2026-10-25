"""
predict_values.py
=================
Weekly: estimates the transfer value of every player of the current season,
with the saved best model, so the front end shows values that follow this
week's stats. The model itself is retrained only after transfer windows
(train_model.py); this script never trains.

    Trusted Zone (this week)  +  exploitation_zone/models/xvalue_xgb_best.joblib
                    │
                    ▼
    exploitation_zone/predictions/latest.parquet          (what the front end reads)
    exploitation_zone/predictions/history/<date>.parquet  (one copy per week)

WHAT THE NUMBER MEANS
    The model was trained on transfers, so it predicts a transfer fee. For a
    player who is not moving, we ask: "what would a club pay for him if he
    moved in the next window?" The transfer-specific inputs are filled in as:
      club, league     his current club and league (the club where he played most minutes)
      window, season   the next transfer window and the season it belongs to
      age              his current age
      nationality,     from his most recent Transfermarkt transfer (same words the
      position         model learned from); empty if he has none
    Running stats and injury history are built with the SAME code and switches
    as the training data (build_features.py).

SETTINGS: TRUSTED_ROOT, EXPLOITATION_ROOT, MINIO_* (same as the other scripts)

RUN:   python predict_values.py
"""

import io
import json
import os
import sys
from datetime import date, datetime

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "exploitation"))   # build_features.py
sys.path.insert(0, HERE)                                         # train_model.py
import build_features as bf      # noqa: E402  same feature code as the training data
import train_model as tm         # noqa: E402  same storage helpers (MinIO or local)


def next_window(today: date):
    """The next (or current) transfer window and the season it belongs to.
    Sep-Jan -> winter window of this season; Feb-Aug -> summer window of next season."""
    start = today.year if today.month >= 7 else today.year - 1     # this season, e.g. 2026
    if today.month in (7, 8):
        return "summer", start          # summer window open now (season already started)
    if today.month in (9, 10, 11, 12, 1):
        return "winter", start
    return "summer", start + 1          # Feb-Jun: next summer belongs to next season


def main():
    today = date.today()
    window, window_season = next_window(today)

    # ── The saved model and the features it expects ──────────────────────
    saved, info = tm.load("models/xvalue_xgb_best.joblib"), tm.load("models/best_metrics.json")
    if saved is None or info is None:
        sys.exit("[ERR] no saved model yet: run train_model.py (xvalue_model_dag) first")
    model = joblib.load(io.BytesIO(saved))
    info = json.loads(info)
    features = info["features"]
    print(f"Model trained {info['timestamp']} (RMSE log {info['metrics']['rmse_log']:.4f}), "
          f"{len(features)} features")

    # ── Current players, with the same features as the training data ─────
    T = bf.root("TRUSTED_ROOT", "s3://xvalue-data/trusted_zone")
    con = bf.connect()
    bf.load_trusted(con, T)
    season = con.sql("SELECT max(season_start) FROM stats").fetchall()[0][0]
    this_season = today.year if today.month >= 7 else today.year - 1
    if season != this_season:
        print(f"[WARN] the newest FBref season in the Trusted Zone is {season}-{(season + 1) % 100:02d}, "
              f"not this season: has the weekly FBref DAG run?")
    # Training row for a transfer in season S used seasons up to S (notebook) or up to
    # S-1 (USE_ONLY_PAST_SEASONS). A move in this season's winter window = season S;
    # a move next summer = season S+1, whose "past" is everything up to now.
    only_past = bf.USE_ONLY_PAST_SEASONS and window_season == season
    bf.build_player_features(con, only_past)
    print(f"Players of season {season}-{(season + 1) % 100:02d}; next window: {window} "
          f"({window_season}-{(window_season + 1) % 100:02d})")

    df = con.sql(f"""
        WITH now AS (
            SELECT player_key,
                   arg_max(player, "Min") AS player_name,
                   arg_max(team, "Min")   AS club,
                   arg_max(league, "Min") AS league,
                   max(age)               AS age
            FROM stats WHERE season_start = {season} GROUP BY player_key),
        last_transfer AS (
            SELECT player_key,
                   arg_max(nationality, season_start) AS nationality,
                   arg_max(position, season_start)    AS position
            FROM transfers GROUP BY player_key)
        SELECT now.*, lt.nationality, lt.position,
               p.* EXCLUDE (player_key, season), f.* EXCLUDE (player_key, season)
        FROM now
        LEFT JOIN last_transfer lt USING (player_key)
        LEFT JOIN players_season p ON p.player_key = now.player_key AND p.season = {season}
        LEFT JOIN features_lesiones f ON f.player_key = now.player_key AND f.season = {season}
    """).df()
    if df.empty:
        sys.exit(f"[ERR] no players found for season {season}")

    if {"avg_PK_acum", "avg_PKatt_acum"} <= set(df.columns):      # as in build_features.py
        df["avg_PK_perc_acum"] = np.where(df["avg_PKatt_acum"] == 0, np.nan,
                                          df["avg_PK_acum"] / df["avg_PKatt_acum"])
    df["season"] = window_season
    df["window"] = window
    df["tiene_historial"] = df["avg_MP_acum"].notna().astype(int) if "avg_MP_acum" in df else 0

    missing = [c for c in features if c not in df.columns]
    if missing:
        print(f"[WARN] features not available, left empty: {missing}")
        for c in missing:
            df[c] = np.nan
    cat = [c for c in features if c in tm.COLS_CAT]
    num = [c for c in features if c not in cat]
    df[num] = df[num].astype("float64").replace([np.inf, -np.inf], np.nan)
    for c in cat:
        df[c] = df[c].astype("object").where(df[c].notna(), np.nan)
    print(f"{len(df):,} players; {df['nationality'].notna().mean():.0%} have a Transfermarkt "
          f"transfer (nationality and position known)")

    # ── Predict ──────────────────────────────────────────────────────────
    df["predicted_value_eur"] = np.maximum(np.expm1(model.predict(df[features])), 0).round(-3)
    out = df[["player_name", "player_key", "club", "league", "age", "nationality", "position",
              "predicted_value_eur"]].copy()
    out["season"] = f"{season}-{(season + 1) % 100:02d}"
    out["next_window"] = f"{window} {window_season}-{(window_season + 1) % 100:02d}"
    out["model_trained_at"] = info["timestamp"]
    out["predicted_at"] = datetime.now().isoformat(timespec="seconds")
    out = out.sort_values("predicted_value_eur", ascending=False).reset_index(drop=True)

    print("\nHighest estimated values:")
    print(out.head(10)[["player_name", "club", "age", "predicted_value_eur"]]
          .to_string(index=False, formatters={"predicted_value_eur": "{:,.0f} €".format}))

    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    tm.save("predictions/latest.parquet", buf.getvalue())
    tm.save(f"predictions/history/{today.isoformat()}.parquet", buf.getvalue())


if __name__ == "__main__":
    main()
