"""
clean_to_trusted.py
===================
THE one cleaning script of the project: Landing Zone -> Trusted Zone (PySpark).

The same code is used for the one-off historical load (backfill) and for the
weekly Airflow run. Only the amount of data it processes changes:

    python clean_to_trusted.py --seasons all              # backfill, once by hand
    python clean_to_trusted.py --seasons current          # weekly, from Airflow
    python clean_to_trusted.py --seasons 2526,2627 --tables fbref_player_stats
    python clean_to_trusted.py --seasons all --dry-run    # report only, write nothing

-----------------------------------------------------------------------
WHAT IT READS (Landing Zone, never modified)
-----------------------------------------------------------------------
    landing_zone/<league>/<league>_<season>_stats_fbref.parquet
    landing_zone/<league>/<league>_<season>_stats_understat.parquet
    landing_zone/<league>/<league>_<season>_transfers_transfermarkt.parquet
    landing_zone/general/<name containing "injur" or "lesion">.parquet
 <season> is a code like 2526 (= 2025-26) or 0001 (= 2000-01).
 Files inside a "snapshots" folder are skipped (weekly archive copies).
 Any other file is listed as "skipped" in the report.

-----------------------------------------------------------------------
WHAT IT WRITES (Trusted Zone)
-----------------------------------------------------------------------
    trusted_zone/fbref_player_stats/league=<league>/season=<2025-26>/
    trusted_zone/understat_player_stats/league=<league>/season=<2025-26>/
    trusted_zone/transfers/league=<league>/season=<2025-26>/
    trusted_zone/injuries/

 Every table that has seasons uses the SAME two season columns:
    season        "2025-26"  (text, also the folder name)
    season_start  2025       (whole number, easy to compare and sort)

 Read any table as ONE table, e.g. in DuckDB:
    SELECT * FROM read_parquet('.../fbref_player_stats/**/*.parquet',
                               hive_partitioning = true)

-----------------------------------------------------------------------
THE CLEANING TECHNIQUES (one function each, applied in this order)
-----------------------------------------------------------------------
 Column NAMES are kept as in the source (Gls, SoT%, Days, fee, ...) so the
 modelling notebooks keep working. Only VALUES are fixed. Columns added by
 this script are in lowercase_with_underscores.

 1. clean_text          trim spaces; "", "nan", "None", "-", "?" -> missing
 2. fix_formats         age "25-363" -> 25, nation "es ESP" -> "ESP",
                        Days "45 days" -> 45, dates stored as text -> real dates
 3. fix_numbers         "1,234" -> 1234, "+12" -> 12: text -> real numbers
 3b. fix_impossible_values  SoT% above 100 -> recalculated from SoT / Sh
 4. set_league_season   league and season come from the landing PATH
                        (fixes the 2627 file that says 2526, missing leagues)
 5. remove_bad_rows     exact duplicates, rows without a player,
                        players who never played (0 matches)
 5b. resolve_repeated_players  same player listed twice (one copy with gaps):
                        keep the most complete row
 6. add_helper_columns  player_key "Kylian Mbappé" -> "kylian mbappe" (for joins),
                        injury_season (the football season of an injury date)
 7. add_lineage         source_file and cleaned_at on every row
 8. quality_checks      any problem -> that file is NOT written, exit code 1

 NOT done here on purpose (combining = Exploitation Zone): merging a player's
 clubs into one row, running averages, joining tables, filtering transfers.

-----------------------------------------------------------------------
SETTINGS (environment variables)
-----------------------------------------------------------------------
    MINIO_ENDPOINT     e.g. localhost:9000 (from inside Docker: minio:9000)
    MINIO_ACCESS_KEY   MinIO user
    MINIO_SECRET_KEY   MinIO password
    LANDING_ROOT       default s3a://xvalue-data/landing_zone
    TRUSTED_ROOT       default s3a://xvalue-data/trusted_zone
 Both roots may also be normal folders (./data/landing_zone) for local tests.
"""

import argparse
import glob
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


# =====================================================================
# 0. SETTINGS: what each kind of file is and how to check it
# =====================================================================

LEAGUES = ["eng-premier-league", "esp-la-liga", "ita-serie-a", "ger-bundesliga", "fra-ligue-1"]

# The end of a landing file name decides which Trusted table it belongs to.
FILE_ENDINGS = {
    "_stats_fbref": "fbref_player_stats",
    "_stats_understat": "understat_player_stats",
    "_transfers_transfermarkt": "transfers",
}
# Files in landing_zone/general/ are recognised by a word in their name.
GENERAL_FILES = {"injuries": ("injur", "lesion")}
ALL_TABLES = [*FILE_ENDINGS.values(), *GENERAL_FILES]

# Per table: which columns are text (all others must be numbers), which
# column holds the player, the club, matches played and minutes, and which
# columns identify a row uniquely.
RULES = {
    "fbref_player_stats": dict(
        text={"league", "season", "team", "player", "nation", "pos", "player_id", "team_id"},
        integers={"age", "born"},
        player="player", club="team", matches="MP", minutes="Min",
        # Old files have no IDs: two players with the same name at one club
        # (e.g. two "Danilo"s) are told apart by their birth year.
        unique=[["player_id", "team_id"], ["player", "team", "born"]],
        check_clubs=True),
    "understat_player_stats": dict(
        text={"league", "season", "team", "player", "position", "player_id", "team_id"},
        integers=set(),
        player="player", club="team", matches="matches", minutes="minutes",
        unique=[["player_id"], ["player", "team"]],
        check_clubs=True),
    "transfers": dict(
        text=None,                       # unknown layout: convert only clear number columns
        must_be_numbers=["fee", "market_value"],
        player="player_name", club="club", matches=None, minutes=None,
        unique=None, check_clubs=False,
        keep_source_league=True),        # Transfermarkt's own league name -> league_source
    "injuries": dict(
        text=None, must_be_numbers=[],
        player="player_name", club=None, matches=None, minutes=None,
        unique=None, check_clubs=False),
}

NEGATIVE_ALLOWED = {"+/-", "+/-90", "On-Off"}   # goal difference can be negative
PERCENT_COLUMNS = {"SoT%", "Min%"}
MISSING_TEXT = ("", "nan", "NaN", "None", "none", "null", "NULL", "-", "?", "n/a", "N/A")


# =====================================================================
# 1. SEASONS
# =====================================================================

def start_from_code(code: str) -> int:
    """'2526' -> 2025, '0001' -> 2000, '9900' -> 1999."""
    yy = int(code[:2])
    return 2000 + yy if yy < 70 else 1900 + yy


def season_label(start: int) -> str:
    """2025 -> '2025-26'."""
    return f"{start}-{(start + 1) % 100:02d}"


def season_code(start: int) -> str:
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def current_season_start(today: date | None = None) -> int:
    """From July on, the new season has started. 24 Oct 2026 -> 2026."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def parse_season_argument(text: str) -> int:
    """'2526', '2025-26' or '2025' -> 2025."""
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2,4}", text):
        return int(text[:4])
    if re.fullmatch(r"\d{4}", text):
        start = start_from_code(text)
        if (start + 1) % 100 == int(text[2:]):
            return start
        return int(text)
    raise ValueError(f"cannot read season '{text}'")


def accepted_season_values(start: int) -> list[str]:
    """All the ways a source may write the season `start` (2025):
    2526, 2025, 2025-26, 2025-2026, 2025/26, 25/26, 2025/2026."""
    yy, zz = f"{start % 100:02d}", f"{(start + 1) % 100:02d}"
    return [yy + zz, str(start), f"{start}-{zz}", f"{start}-{start + 1}",
            f"{start}/{zz}", f"{yy}/{zz}", f"{start}/{start + 1}"]


def expected_clubs(league: str, start: int) -> int:
    if league == "ger-bundesliga":
        return 18
    if league == "fra-ligue-1":
        return 18 if start >= 2023 or start <= 2001 else 20
    if league == "ita-serie-a":
        return 18 if start <= 2003 else 20
    return 20


# =====================================================================
# 2. SPARK AND MINIO
# =====================================================================

def hadoop_version() -> str:
    """The S3 add-on (hadoop-aws) must match Spark's own Hadoop version
    exactly, so we read that version from Spark's files."""
    import pyspark
    jars = glob.glob(os.path.join(os.path.dirname(pyspark.__file__),
                                  "jars", "hadoop-client-api-*.jar"))
    found = re.search(r"hadoop-client-api-([\d.]+)\.jar", jars[0]) if jars else None
    return found.group(1) if found else "3.4.1"


def minio_endpoint() -> str:
    endpoint = os.environ["MINIO_ENDPOINT"]
    return endpoint if endpoint.startswith("http") else "http://" + endpoint


def build_spark(uses_s3: bool) -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("clean_to_trusted")
        .master("local[2]")                        # 2 CPU cores on the VM
        .config("spark.driver.memory", "1g")       # small VM, small data
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        # A value that can't be converted becomes null (and is counted and
        # reported) instead of crashing the job. Spark 3.5 default; Spark 4 needs it.
        .config("spark.sql.ansi.enabled", "false")
        # Overwrite ONLY the league/season folders being written, keep the rest.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    )
    if uses_s3:
        endpoint = minio_endpoint()
        builder = (
            builder
            # Downloaded automatically the first time (about 500 MB), then kept in
            # ~/.ivy2. In Docker, mount a volume on that folder so it survives
            # container restarts (Spark 4's own default, ~/.ivy2.5.2, would not).
            .config("spark.jars.packages", f"org.apache.hadoop:hadoop-aws:{hadoop_version()}")
            .config("spark.jars.ivy", os.environ.get("SPARK_IVY_DIR",
                                                     os.path.expanduser("~/.ivy2")))
            .config("spark.hadoop.fs.s3a.endpoint", endpoint)
            .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")  # any value; MinIO ignores it
            .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ACCESS_KEY"])
            .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_SECRET_KEY"])
            .config("spark.hadoop.fs.s3a.path.style.access", "true")       # needed for MinIO
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled",
                    str(endpoint.startswith("https")).lower())
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def list_parquet_files(root: str) -> list[str]:
    """All .parquet files under root, as paths relative to root."""
    if root.startswith("s3a://"):
        from minio import Minio
        bucket, _, prefix = root[len("s3a://"):].partition("/")
        endpoint = minio_endpoint()
        client = Minio(re.sub(r"^https?://", "", endpoint),
                       access_key=os.environ["MINIO_ACCESS_KEY"],
                       secret_key=os.environ["MINIO_SECRET_KEY"],
                       secure=endpoint.startswith("https"))
        prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        names = [o.object_name for o in client.list_objects(bucket, prefix, recursive=True)]
        return sorted(n[len(prefix):] for n in names if n.endswith(".parquet"))
    files = glob.glob(os.path.join(root, "**", "*.parquet"), recursive=True)
    return sorted(os.path.relpath(f, root).replace(os.sep, "/")
                  for f in files if os.path.isfile(f))


def join_path(root: str, rel: str) -> str:
    return f"{root.rstrip('/')}/{rel}"


# =====================================================================
# 3. WHICH FILE IS WHAT
# =====================================================================

def classify(files: list[str]):
    """Returns ({table: [(path, league, season_start)]}, {table: [path]}, [skipped])."""
    seasonal = {t: [] for t in FILE_ENDINGS.values()}
    general = {t: [] for t in GENERAL_FILES}
    skipped = []
    for rel in files:
        parts = rel.split("/")
        name = parts[-1].lower()
        if "snapshots" in parts:
            continue                                       # weekly archive copies
        if parts[0] in LEAGUES:
            match = re.fullmatch(rf"{re.escape(parts[0])}_(\d{{4}})(_[a-z_]+)\.parquet", name)
            table = FILE_ENDINGS.get(match.group(2)) if match else None
            if table and (start_from_code(match.group(1)) + 1) % 100 == int(match.group(1)[2:]):
                seasonal[table].append((rel, parts[0], start_from_code(match.group(1))))
                continue
        elif parts[0] == "general":
            table = next((t for t, words in GENERAL_FILES.items()
                          if any(w in name for w in words)), None)
            if table:
                general[table].append(rel)
                continue
        skipped.append(rel)
    return seasonal, general, skipped


# =====================================================================
# 4. THE CLEANING TECHNIQUES
# =====================================================================

def col(name: str):
    """Column by name, safe for names like 'SoT%' or 'Games missed'."""
    return F.col(f"`{name}`")


def clean_text(df: DataFrame) -> DataFrame:
    """Technique 1: STANDARDISE MISSING VALUES. Trim text and turn
    'empty-looking' text into real missing values (null)."""
    for field in df.schema.fields:
        if isinstance(field.dataType, T.StringType):
            c = F.trim(col(field.name))
            df = df.withColumn(field.name, F.when(c.isin(*MISSING_TEXT), None).otherwise(c))
    return df


def first_integer(name: str):
    """'25-363' -> 25, '45 days' -> 45, '12.0' -> 12."""
    return F.regexp_extract(col(name).cast("string"), r"(\d+)", 1).cast("int")


def fix_formats(df: DataFrame, problems: list) -> DataFrame:
    """Technique 2: PARSE SOURCE-SPECIFIC FORMATS."""
    for name in ("age", "born", "player_age", "Days", "Games missed"):
        if name in df.columns:
            df = df.withColumn(name, first_integer(name))
    if "nation" in df.columns:                          # "es ESP" -> "ESP"
        df = df.withColumn("nation", F.element_at(F.split("nation", " "), -1))
    for name in [c for c in df.columns if c.endswith(("_parsed", "_date"))]:
        if isinstance(df.schema[name].dataType, T.StringType):   # text -> real date
            bad = df.filter(col(name).isNotNull() & F.to_date(col(name)).isNull()).count()
            if bad:
                problems.append(f"{bad} values of '{name}' are not dates")
            df = df.withColumn(name, F.to_date(col(name)))
    return df


def as_number(name: str):
    """'1,234' -> 1234.0, '+12' -> 12.0, '€' and spaces removed. Not a number -> null."""
    return F.regexp_replace(col(name).cast("string"), r"[,+\s€$£]", "").cast("double")


def fix_numbers(df: DataFrame, rules: dict, problems: list) -> DataFrame:
    """Technique 3: TYPE CONVERSION (text -> numbers), measured in ONE pass.
    - Stats tables: every column not listed as text MUST be a number.
      A value that is not a number is a PROBLEM (the file is refused).
    - Other tables: listed columns must be numbers; any other text column
      is converted only if ALL its values are numbers."""
    text_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, T.StringType)]
    if rules["text"] is not None:
        must = [c for c in df.columns if c not in rules["text"] and c != "source_file"]
        optional = []
    else:
        must = [c for c in rules["must_be_numbers"] if c in df.columns]
        optional = [c for c in text_cols if c not in must and not c.endswith("_id")
                    and c not in ("player_name", "player", "club", "team", "season",
                                  "league", "source_file")]
    measure = [c for c in must + optional if c in text_cols]
    stats = {}
    if measure:
        stats = df.agg(*[a for c in measure for a in (
            F.count(col(c)).alias(f"{c}|n"),
            F.count(as_number(c)).alias(f"{c}|num"),
            F.sum((as_number(c) == F.floor(as_number(c))).cast("int")).alias(f"{c}|whole"),
            F.first(F.when(as_number(c).isNull(), col(c)), ignorenulls=True).alias(f"{c}|bad"),
        )]).first().asDict()
    for c in must:
        if c in text_cols:
            bad = stats[f"{c}|n"] - stats[f"{c}|num"]
            if bad:
                problems.append(f"column '{c}': {bad} values are not numbers "
                                f"(e.g. '{stats[c + '|bad']}')")
            df = df.withColumn(c, as_number(c))
        else:
            df = df.withColumn(c, col(c).cast("double"))
    for c in optional:
        n, num, whole = stats[f"{c}|n"], stats[f"{c}|num"], stats[f"{c}|whole"] or 0
        if n and num == n:
            df = df.withColumn(c, as_number(c).cast("long" if whole == n else "double"))
    for c in rules.get("integers", set()) & set(df.columns):
        df = df.withColumn(c, col(c).cast("int"))
    return df


def fix_impossible_values(df: DataFrame, warnings: list) -> DataFrame:
    """Technique 3b: REPAIR IMPOSSIBLE VALUES. A percentage above 100 can't be
    right. Recalculate it from the raw counts when they make sense, otherwise
    leave it empty. One wrong cell should not throw away a whole season."""
    if all(c in df.columns for c in ("SoT%", "Sh", "SoT")):
        bad = col("SoT%") > 100
        n = df.filter(bad).count()
        if n:
            counts_ok = (col("Sh") > 0) & (col("SoT") <= col("Sh"))
            df = df.withColumn("SoT%", F.when(bad & counts_ok, F.round(col("SoT") / col("Sh") * 100, 1))
                                        .when(bad, None).otherwise(col("SoT%")))
            warnings.append(f"{n} SoT% value(s) above 100: recalculated as SoT / Sh "
                            f"(left empty where the counts are impossible too)")
    if "Min%" in df.columns:
        n = df.filter(col("Min%") > 100).count()
        if n:
            df = df.withColumn("Min%", F.when(col("Min%") > 100, None).otherwise(col("Min%")))
            warnings.append(f"{n} Min% value(s) above 100: left empty")
    return df


def set_league_season(df: DataFrame, league: str, start: int, rules: dict,
                      warnings: list) -> DataFrame:
    """Technique 4: TRUST THE PATH. League and season are taken from the landing
    path; a file whose own season column disagrees is relabelled with a warning."""
    if "season" in df.columns:
        as_text = F.regexp_replace(col("season").cast("string"), r"\.0$", "")
        wrong = df.filter(as_text.isNotNull()
                          & ~as_text.isin(*accepted_season_values(start))).count()
        if wrong:
            said = sorted(r[0] for r in df.select(as_text).distinct().limit(3).collect())
            warnings.append(f"season column said {said}, path says "
                            f"{season_label(start)}: {wrong} rows relabelled")
    if "league" in df.columns:
        if rules.get("keep_source_league"):
            df = df.withColumnRenamed("league", "league_source")
        else:
            missing = df.filter(col("league").isNull()).count()
            if missing:
                warnings.append(f"{missing} rows had no league: set to {league}")
    return (df.withColumn("league", F.lit(league))
              .withColumn("season", F.lit(season_label(start)))
              .withColumn("season_start", F.lit(start)))


def resolve_repeated_players(df: DataFrame, warnings: list) -> DataFrame:
    """Technique 5b: KEEP THE MOST COMPLETE COPY. Old FBref files (no player IDs)
    sometimes list the same appearance twice: one complete row and one copy
    with gaps (e.g. no age/birth year). Adding them up would double-count, so
    we keep ONE row: the one with the most filled-in values, then most minutes.
    Only for rows with the same name and club whose birth years don't conflict
    (same, or missing). Namesakes with different birth years are kept."""
    if not {"player", "team", "born"} <= set(df.columns):
        return df
    if "player_id" in df.columns and df.filter(col("player_id").isNull()).count() == 0:
        return df                                       # IDs available: nothing to guess
    from pyspark.sql import Window
    group = Window.partitionBy("player", "team")
    filled = sum(F.when(col(c).isNotNull(), 1).otherwise(0) for c in df.columns)
    minutes = col("Min") if "Min" in df.columns else F.lit(0)
    ranked = (df.withColumn("_n", F.count("*").over(group))
                .withColumn("_births", F.size(F.collect_set("born").over(group)))
                .withColumn("_rank", F.row_number().over(
                    group.orderBy(filled.desc(), F.coalesce(minutes, F.lit(0)).desc()))))
    same_person = (col("_n") > 1) & (col("_births") <= 1)
    dropped = ranked.filter(same_person & (col("_rank") > 1))
    n = dropped.count()
    if n:
        names = sorted({f"{r['player']} ({r['team']})" for r in dropped.select("player", "team").collect()})
        warnings.append(f"{n} repeated row(s) of the same player removed, most complete row kept: "
                        f"{', '.join(names[:5])}{' ...' if len(names) > 5 else ''}")
    return ranked.filter(~(same_person & (col("_rank") > 1))).drop("_n", "_births", "_rank")


def remove_bad_rows(df: DataFrame, rules: dict, report: dict) -> DataFrame:
    """Technique 5: DEDUPLICATION AND FILTERING."""
    report["rows_in"] = df.count()
    df = df.dropDuplicates()
    report["duplicates"] = report["rows_in"] - df.count()
    before = df.count()
    df = df.filter(col(rules["player"]).isNotNull())
    report["no_player"] = before - df.count()
    if rules["matches"] in df.columns:
        before = df.count()
        df = df.filter(F.coalesce(col(rules["matches"]), F.lit(0)) > 0)
        report["no_matches"] = before - df.count()
    return df


def key_text(text):
    """Technique 6a: NAME NORMALISATION. '  Kylian Mbappé ' -> 'kylian mbappe'.
    The SAME rule in every table, so players and clubs can be matched."""
    if text is None:
        return None
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() or None


key_udf = F.udf(key_text, T.StringType())


def add_helper_columns(df: DataFrame) -> DataFrame:
    """Technique 6: DERIVED COLUMNS. Original columns are never changed."""
    for name, key in (("player", "player_key"), ("player_name", "player_key"),
                      ("team", "team_key"), ("club", "club_key")):
        if name in df.columns and key not in df.columns:
            df = df.withColumn(key, key_udf(col(name)))
    if "injury_from_parsed" in df.columns:
        # 6b: the football season of an injury: March 2026 belongs to 2025-26.
        d = col("injury_from_parsed")
        start = F.when(F.month(d) >= 7, F.year(d)).otherwise(F.year(d) - 1)
        df = (df.withColumn("injury_season_start", start)
                .withColumn("injury_season", F.concat(
                    start.cast("string"), F.lit("-"),
                    F.lpad(((start + 1) % 100).cast("string"), 2, "0"))))
    return df


def add_lineage(df: DataFrame, source_file: str | None) -> DataFrame:
    """Technique 7: LINEAGE. Where every row came from and when it was cleaned."""
    if source_file is not None:
        df = df.withColumn("source_file", F.lit(source_file))
    return df.withColumn("cleaned_at", F.lit(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))


# =====================================================================
# 5. QUALITY CHECKS (technique 8: VALIDATION RULES)
# =====================================================================

def quality_checks(df: DataFrame, rules: dict, league: str | None,
                   start: int | None) -> list[str]:
    problems = []
    if df.count() == 0:
        return ["no rows left after cleaning"]
    needed = [c for c in (rules["player"], rules["club"], rules["matches"], rules["minutes"]) if c]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return [f"missing column(s) {missing}"]

    games = None
    if rules["check_clubs"]:
        # Understat writes a player who changed club as "Club A,Club B".
        clubs = (df.select(F.explode(F.split(col(rules["club"]), ",")).alias("c"))
                   .select(F.trim("c")).distinct().count())
        expected = expected_clubs(league, start)
        games = 2 * (expected - 1)
        if clubs != expected:
            problems.append(f"{clubs} clubs, expected {expected}")

    # Use the first key that works: IDs only if every row has them;
    # the last key (names) is always usable.
    keys = [k for k in (rules["unique"] or []) if all(c in df.columns for c in k)]
    for i, key in enumerate(keys):
        last = i == len(keys) - 1
        if not last and df.filter(" OR ".join(f"`{c}` IS NULL" for c in key)).count():
            continue
        dupes = df.groupBy(*[col(c) for c in key]).count().filter("count > 1")
        n = dupes.count()
        if n:
            names = ", ".join(" / ".join(str(v) for v in r[:-1]) for r in dupes.limit(3).collect())
            problems.append(f"{n} rows share the same {'+'.join(key)}: {names}")
        break

    numeric = [f.name for f in df.schema.fields if isinstance(f.dataType, T.NumericType)
               and f.name not in ("season_start", "injury_season_start")]
    if numeric:
        lim = df.agg(*[F.min(col(c)).alias(f"min|{c}") for c in numeric],
                     *[F.max(col(c)).alias(f"max|{c}") for c in numeric]).first().asDict()
        negative = [c for c in numeric if c not in NEGATIVE_ALLOWED
                    and lim[f"min|{c}"] is not None and lim[f"min|{c}"] < 0]
        if negative:
            problems.append(f"negative values in {negative}")
        over = [c for c in PERCENT_COLUMNS if c in numeric and (lim[f"max|{c}"] or 0) > 100]
        if over:
            problems.append(f"percentages above 100 in {over}")
        if games:
            top_matches = lim.get(f"max|{rules['matches']}") or 0
            top_minutes = lim.get(f"max|{rules['minutes']}") or 0
            if top_matches > games:
                problems.append(f"{rules['matches']} up to {top_matches:g}, season has {games} matchdays")
            if top_minutes > games * 100:
                problems.append(f"{rules['minutes']} up to {top_minutes:g}, impossible in {games} matches")
    return problems


# =====================================================================
# 6. CLEAN ONE INPUT
# =====================================================================

def clean(spark, landing, table, rels, league=None, start=None) -> DataFrame | None:
    rules = RULES[table]
    where = f" | {league} | {season_label(start)}" if league else ""
    print(f"\n=== {', '.join(rels)}\n    {table}{where}")
    warnings, problems, report = [], [], {}
    try:
        parts = [clean_text(spark.read.parquet(join_path(landing, r)))
                 .withColumn("source_file", F.lit(r)) for r in rels]
        df = parts[0]
        for part in parts[1:]:
            df = df.unionByName(part, allowMissingColumns=True)
        df = fix_formats(df, problems)
        df = fix_numbers(df, rules, problems)
        df = fix_impossible_values(df, warnings)
        if "is_loan" in df.columns:                      # True/False/"1"/"0" -> 1/0
            v = F.lower(col("is_loan").cast("string"))
            df = df.withColumn("is_loan", F.when(v.isin("1", "true", "1.0", "yes"), 1)
                               .when(v.isin("0", "false", "0.0", "no"), 0).cast("int"))
        if league:
            df = set_league_season(df, league, start, rules, warnings)
        df = remove_bad_rows(df, rules, report)
        df = resolve_repeated_players(df, warnings)
        df = add_helper_columns(df)
        df = add_lineage(df, None).cache()
        problems += quality_checks(df, rules, league, start)
    except Exception as error:
        print(f"    FAILED: {str(error).strip().splitlines()[0]}")
        return None
    rows_out = df.count()
    extra = f", no matches {report['no_matches']}" if "no_matches" in report else ""
    print(f"    rows in {report['rows_in']} -> out {rows_out}  (duplicates "
          f"{report['duplicates']}, no player {report['no_player']}{extra})")
    for w in warnings:
        print(f"    WARNING: {w}")
    for p in problems:
        print(f"    PROBLEM: {p}")
    if problems:
        print("    -> NOT written to trusted")
        return None
    return df


# =====================================================================
# 7. MAIN
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Clean Landing Zone into Trusted Zone")
    parser.add_argument("--seasons", default="current",
                        help="'all', 'current' (default) or a list like 2526,2627 or 2025-26")
    parser.add_argument("--tables", default="all",
                        help=f"'all' or a list from: {', '.join(ALL_TABLES)}")
    parser.add_argument("--dry-run", action="store_true", help="clean and report, write nothing")
    args = parser.parse_args()

    landing = os.environ.get("LANDING_ROOT", "s3a://xvalue-data/landing_zone")
    trusted = os.environ.get("TRUSTED_ROOT", "s3a://xvalue-data/trusted_zone")
    tables = ALL_TABLES if args.tables == "all" else args.tables.split(",")
    if set(tables) - set(ALL_TABLES):
        sys.exit(f"unknown table(s): {set(tables) - set(ALL_TABLES)}")
    starts = (None if args.seasons == "all"
              else [current_season_start()] if args.seasons == "current"
              else [parse_season_argument(s) for s in args.seasons.split(",")])

    seasonal, general, skipped = classify(list_parquet_files(landing))
    print(f"Landing: {landing}\nTrusted: {trusted}\nSeasons: "
          f"{', '.join(season_label(s) for s in starts) if starts else 'all'} | "
          f"tables: {', '.join(tables)}{' | DRY RUN' if args.dry_run else ''}")
    for s in skipped:
        print(f"  skipped (not recognised): {s}")

    spark = build_spark("s3a://" in landing + trusted)
    written, failed = [], []

    # Seasonal tables: one folder per league and season. Weekly runs only
    # replace the season folders they clean; all other seasons stay as they are.
    for table in FILE_ENDINGS.values():
        if table not in tables:
            continue
        todo = [f for f in seasonal[table] if starts is None or f[2] in starts]
        if not todo:
            print(f"\n=== {table}: no landing files for these seasons")
            continue
        good = []
        for rel, league, start in todo:
            df = clean(spark, landing, table, [rel], league, start)
            (good.append(df) if df is not None else failed.append(rel))
        if good:
            out = good[0]
            for df in good[1:]:
                out = out.unionByName(df, allowMissingColumns=True)
            path = join_path(trusted, table)
            if not args.dry_run:
                # repartition: gather each league-season's rows into ONE task, so each
                # folder gets ONE file instead of several tiny ones.
                (out.repartition("league", "season")
                    .write.mode("overwrite").partitionBy("league", "season").parquet(path))
            written.append(f"{path}  ({len(good)} league-season folders)")

    # General tables: rebuilt completely (only in a full run, they have no season).
    for table in GENERAL_FILES:
        if table not in tables or starts is not None:
            continue
        if not general[table]:
            print(f"\n=== {table}: no file found in general/")
            failed.append(table)
            continue
        df = clean(spark, landing, table, general[table])
        if df is None:
            failed.append(table)
            continue
        path = join_path(trusted, table)
        if not args.dry_run:
            df.coalesce(1).write.mode("overwrite").parquet(path)
        written.append(path)

    spark.stop()
    print(f"\n{'Would write' if args.dry_run else 'Written'}:")
    for w in written:
        print(f"  {w}")
    if failed:
        print("FAILED (nothing written for these):")
        for f in failed:
            print(f"  {f}")
    sys.exit(1 if failed else 0)     # Airflow shows the task red on exit code 1


if __name__ == "__main__":
    main()