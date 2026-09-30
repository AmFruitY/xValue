"""Build the modelling dataset (``df_xvalue``) for the xValue project.

The script merges three sources into one player-season table:

1. FBref player statistics (``all_players.parquet``), aggregated per
   player-season and accumulated over each player's career.
2. Injury history (``dataset_lesiones.parquet``), summarised into one row of
   features per player.
3. Transfers (CSV files), restricted to permanent incoming transfers.

It uses DuckDB's PySpark-compatible API (``duckdb.experimental.spark``), so no
Spark installation is required.

Usage:
    python -m etl.preprocessing \\
        --parquet-dir data/parquet \\
        --transfers-dir data/transfers \\
        --output data/parquet/df_xvalue.parquet
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
from duckdb.experimental.spark.sql import DataFrame, SparkSession
from duckdb.experimental.spark.sql import functions as F

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLAYER_STATS_FILE = "all_players.parquet"
INJURIES_FILE = "dataset_lesiones.parquet"
TRANSFERS_MERGED_FILE = "transfers_merged.parquet"

# Rows without a league in the source data belong to the Bundesliga.
DEFAULT_LEAGUE = "Bundesliga"

# Columns that are neither averaged nor accumulated.
NON_AVERAGED_COLUMNS = frozenset(
    {"league", "season", "team", "nation", "pos", "age", "born", "player_name"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quote(identifier: str) -> str:
    """Quote a column name for safe use inside a SQL string."""
    return '"' + identifier.replace('"', '""') + '"'


def _sql_path(path: Path) -> str:
    """Return a path formatted for use inside a single-quoted SQL literal."""
    return path.as_posix().replace("'", "''")


def _first_row_per_player(
    df: DataFrame, order_by: str, columns: list
) -> DataFrame:
    """Keep one row per player: the first one under ``order_by``."""
    return (
        df.withColumn(
            "rn",
            F.expr(f"row_number() OVER (PARTITION BY player_name ORDER BY {order_by})"),
        )
        .filter(F.col("rn") == 1)
        .select("player_name", *columns)
    )


# ---------------------------------------------------------------------------
# Player statistics
# ---------------------------------------------------------------------------

def load_player_stats(spark: SparkSession, path: Path) -> DataFrame:
    """Load FBref stats and normalise league, player name and season columns."""
    df = spark.read.parquet(str(path))
    df = df.withColumn("league", F.coalesce(F.col("league"), F.lit(DEFAULT_LEAGUE)))
    df = df.withColumnRenamed("player", "player_name")
    # Season codes start with the two-digit starting year (e.g. "2122" -> 2021).
    df = df.withColumn(
        "season",
        F.substring(F.col("season").cast("string"), 1, 2).cast("int") + 2000,
    )
    return df


def aggregate_by_season(spark: SparkSession, df: DataFrame) -> tuple[DataFrame, list[str]]:
    """Average the numeric columns per player and season.

    A player can have several rows in the same season (e.g. a mid-season
    transfer), so the stats are averaged and the number of teams is counted.

    Returns the aggregated DataFrame and the list of averaged columns.
    """
    averaged_cols = [c for c in df.columns if c not in NON_AVERAGED_COLUMNS]
    df.createOrReplaceTempView("stats")

    avg_exprs = ",\n        ".join(
        f"avg({_quote(c)}) AS {_quote(c)}" for c in averaged_cols
    )
    query = f"""
        SELECT
            player_name,
            season,
            COUNT(DISTINCT "team") AS num_equipos_season,
            {avg_exprs}
        FROM stats
        GROUP BY player_name, season
    """
    return spark.sql(query), averaged_cols


def add_cumulative_stats(
    spark: SparkSession, df_season: DataFrame, averaged_cols: list[str]
) -> DataFrame:
    """Compute career-to-date averages of each stat, up to every season."""
    df_season.createOrReplaceTempView("stats_season")

    cumulative_exprs = ",\n        ".join(
        f'avg({_quote(c)}) OVER w AS {_quote(f"avg_{c}_acum")}' for c in averaged_cols
    )
    query = f"""
        SELECT
            player_name,
            season,
            {cumulative_exprs},
            SUM(num_equipos_season) OVER w AS num_equipos_acum
        FROM stats_season
        WINDOW w AS (
            PARTITION BY player_name
            ORDER BY season
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    """
    return spark.sql(query)


# ---------------------------------------------------------------------------
# Injuries
# ---------------------------------------------------------------------------

def load_injuries(spark: SparkSession, path: Path) -> DataFrame:
    """Load the injury records and parse the number of days out as an integer."""
    df = spark.read.parquet(str(path))
    return df.withColumn(
        "Days", F.regexp_extract(F.col("Days"), r"(\d+)", 1).cast("int")
    )


def build_injury_features(df_injuries: DataFrame) -> DataFrame:
    """Summarise the injury history into one row of features per player."""
    # Basic aggregates.
    features = df_injuries.groupBy("player_name").agg(
        F.sum("Days").alias("total_days_out"),
        F.sum("Games missed").alias("total_games_missed"),
        F.expr("count(distinct Injury)").alias("n_distinct_injuries"),
        F.count("Injury").alias("n_injury_records"),
    )

    # Recurrence of the same injury.
    injury_counts = df_injuries.groupBy("player_name", "Injury").agg(
        F.count("Injury").alias("n_times")
    )
    max_repeat = injury_counts.groupBy("player_name").agg(
        F.max("n_times").alias("max_same_injury_repeats")
    )
    # DuckDB's relational API requires a distinct alias on each side of a join.
    features = (
        features.alias("agg")
        .join(max_repeat.alias("max_repeat"), on="player_name", how="left")
        .withColumn(
            "has_recurrent_injury", (F.col("max_same_injury_repeats") > 1).cast("int")
        )
    )

    # Age at the most recent and at the first injury.
    age_last = _first_row_per_player(
        df_injuries,
        "injury_from_parsed DESC",
        [F.col("player_age").alias("age_at_last_injury")],
    )
    age_first = _first_row_per_player(
        df_injuries,
        "injury_from_parsed ASC",
        [F.col("player_age").alias("age_at_first_injury")],
    )

    # Injury that kept the player out the longest.
    worst = _first_row_per_player(
        df_injuries,
        "Days DESC",
        [
            F.col("Injury").alias("worst_injury_type"),
            F.col("Days").alias("worst_injury_days"),
        ],
    )

    for alias, extra in (("age_last", age_last), ("age_first", age_first), ("worst", worst)):
        features = features.join(extra.alias(alias), on="player_name", how="left")
    return features


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

def merge_transfer_csvs(transfers_dir: Path, output_path: Path) -> None:
    """Merge every transfers CSV into a single Parquet file.

    CSVs may have different columns, so they are unified by column name.
    """
    pattern = _sql_path(transfers_dir / "*.csv")
    duckdb.sql(
        f"""
        COPY (
            SELECT * FROM read_csv('{pattern}', union_by_name=True)
        ) TO '{_sql_path(output_path)}' (FORMAT PARQUET)
        """
    )


def load_incoming_transfers(spark: SparkSession, path: Path) -> DataFrame:
    """Keep permanent incoming transfers (no loans) and drop duplicates."""
    df = spark.read.parquet(str(path))
    df = df.filter((F.col("movement") == "in") & (F.col("is_loan") == 0))
    return df.dropDuplicates()


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def log_join_diagnostics(
    df_players: DataFrame, df_injury_features: DataFrame, df_final: DataFrame
) -> None:
    """Log how well the sources match each other (informative only)."""
    only_players = df_players.join(
        df_injury_features, on="player_name", how="left_anti"
    ).count()
    only_injuries = df_injury_features.join(
        df_players, on="player_name", how="left_anti"
    ).count()
    duplicated_keys = (
        df_final.groupBy(["player_name", "season"])
        .count()
        .filter(F.col("count") > 1)
        .count()
    )
    logger.info("Player-season rows with no injury record match: %d", only_players)
    logger.info("Players with injuries but no stats match: %d", only_injuries)
    logger.info("Duplicated (player_name, season) keys in final table: %d", duplicated_keys)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_dataset(
    parquet_dir: Path,
    transfers_dir: Path,
    output_path: Path,
    run_diagnostics: bool = False,
) -> None:
    """Run the full preprocessing pipeline and write the final Parquet file."""
    spark = SparkSession.builder.getOrCreate()

    logger.info("Building cumulative player stats")
    stats = load_player_stats(spark, parquet_dir / PLAYER_STATS_FILE)
    stats_season, averaged_cols = aggregate_by_season(spark, stats)
    players_season = add_cumulative_stats(spark, stats_season, averaged_cols)

    logger.info("Building injury features")
    injuries = load_injuries(spark, parquet_dir / INJURIES_FILE)
    injury_features = build_injury_features(injuries)
    players_injuries = players_season.join(injury_features, on="player_name", how="left")

    logger.info("Loading transfers")
    merged_transfers = parquet_dir / TRANSFERS_MERGED_FILE
    merge_transfer_csvs(transfers_dir, merged_transfers)
    transfers_in = load_incoming_transfers(spark, merged_transfers)

    logger.info("Joining transfers with player stats and injuries")
    df_final = transfers_in.join(
        players_injuries, on=["player_name", "season"], how="left"
    )

    if run_diagnostics:
        log_join_diagnostics(players_season, injury_features, df_final)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_final.write.parquet(str(output_path))
    logger.info("Dataset written to %s", output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the xValue modelling dataset from stats, injuries and transfers."
    )
    parser.add_argument(
        "--parquet-dir",
        type=Path,
        default=Path("data/parquet"),
        help=f"Folder with {PLAYER_STATS_FILE} and {INJURIES_FILE} "
        "(the merged transfers file is also written here).",
    )
    parser.add_argument(
        "--transfers-dir",
        type=Path,
        default=Path("data/transfers"),
        help="Folder with the transfers CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/parquet/df_xvalue.parquet"),
        help="Path of the final Parquet file.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Log how many players fail to match between sources.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    build_dataset(args.parquet_dir, args.transfers_dir, args.output, args.diagnostics)


if __name__ == "__main__":
    main()
