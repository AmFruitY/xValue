"""
limpieza_spark.py
─────────────────
PySpark script that reads raw landing data from MinIO, applies data cleaning
and transformation, and writes trusted Parquet files back to MinIO.
"""

import os
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, trim, regexp_replace, when, lit, current_date, datediff, to_date

# ── Read configuration from environment variables ─────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "xvalue-data")

def get_spark_session() -> SparkSession:
    """Initialize a SparkSession with Hadoop AWS packages for MinIO/S3 access."""
    # We use Hadoop 3.3.4 dependencies to ensure compatibility with recent PySpark/Java versions.
    return (
        SparkSession.builder
        .appName("xValue_Limpieza_Spark")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262")
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT.replace("http://", "")) # some hadoop versions prefer host:port
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

def clean_column_names(df):
    """Normalize column names."""
    for col_name in df.columns:
        new_col_name = (
            col_name.strip().lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
        )
        # Keep only alphanumeric and underscore
        new_col_name = "".join(c for c in new_col_name if c.isalnum() or c == '_')
        df = df.withColumnRenamed(col_name, new_col_name)
    return df

def clean_money_expr(column_name):
    """Returns a PySpark Column expression that cleans currency strings to floats."""
    c = lower(trim(col(column_name)))
    c = regexp_replace(c, "€", "")
    c = regexp_replace(c, ",", "")
    
    # Handle multipliers
    multiplier = when(c.like("%m%"), 1000000).when(c.like("%k%"), 1000).otherwise(1)
    
    # Extract only numeric characters and decimals
    numeric_str = regexp_replace(c, "[^0-9.]", "")
    
    # Return as float * multiplier
    return when(numeric_str != "", numeric_str.cast("float") * multiplier).otherwise(None)

def clean_percentage_expr(column_name):
    """Returns a PySpark Column expression that cleans percentage strings to floats."""
    c = regexp_replace(col(column_name), "%", "")
    return (trim(c).cast("float") / 100.0)

def main():
    spark = get_spark_session()
    
    # Define S3 paths
    base_s3 = f"s3a://{MINIO_BUCKET}"
    injuries_path = f"{base_s3}/landing/injuries/raw_injuries.csv"
    stats_path = f"{base_s3}/landing/player_stats/raw_u23_player_stats.csv"
    
    trusted_injuries_out = f"{base_s3}/trusted/trusted_injuries.parquet"
    trusted_stats_out = f"{base_s3}/trusted/trusted_u23_player_stats.parquet"

    # =========================
    # 1. Clean Injuries
    # =========================
    print("Reading and cleaning injuries dataset...")
    injuries_df = spark.read.csv(injuries_path, header=True, inferSchema=True)
    injuries_df = clean_column_names(injuries_df)

    # Convert text columns
    text_columns = ["player_name", "player", "club", "team", "injury", "injury_type", "season", "position"]
    for c in text_columns:
        if c in injuries_df.columns:
            injuries_df = injuries_df.withColumn(c, trim(col(c)))

    # Dates
    date_columns = ["injury_start", "injury_end", "from", "until", "date"]
    for c in date_columns:
        if c in injuries_df.columns:
            # Cast to date (assumes standard format, if not you may need to_date(col(c), 'yyyy-MM-dd'))
            injuries_df = injuries_df.withColumn(c, to_date(col(c)))

    # Days Out
    if "days_out" in injuries_df.columns:
        injuries_df = injuries_df.withColumn("days_out", regexp_replace(col("days_out"), "[^0-9]", "").cast("float"))
    elif "injury_start" in injuries_df.columns and "injury_end" in injuries_df.columns:
        injuries_df = injuries_df.withColumn("days_out", datediff(col("injury_end"), col("injury_start")).cast("float"))

    # Rules
    if "days_out" in injuries_df.columns:
        injuries_df = injuries_df.filter(col("days_out").isNull() | (col("days_out") >= 0))

    # Deduplicate
    subset_cols = [c for c in ["player_name", "injury_start", "injury_type", "days_out"] if c in injuries_df.columns]
    if subset_cols:
        injuries_df = injuries_df.dropDuplicates(subset_cols)
    else:
        injuries_df = injuries_df.dropDuplicates()

    injuries_df = injuries_df.withColumn("trusted_load_date", current_date())

    # Write to MinIO
    print(f"Writing injuries to {trusted_injuries_out}")
    injuries_df.write.mode("overwrite").parquet(trusted_injuries_out)

    # =========================
    # 2. Clean Stats
    # =========================
    print("Reading and cleaning u23 player stats...")
    stats_df = spark.read.csv(stats_path, header=True, inferSchema=True)
    stats_df = clean_column_names(stats_df)

    # Rename mins
    if "mins" in stats_df.columns and "minutes" not in stats_df.columns:
        stats_df = stats_df.withColumnRenamed("mins", "minutes")

    # Clean money
    if "market_value" in stats_df.columns:
        stats_df = stats_df.withColumn("market_value", clean_money_expr("market_value"))
    if "salary" in stats_df.columns:
        stats_df = stats_df.withColumn("salary", clean_money_expr("salary"))

    # Clean percentages
    percentage_columns = [c for c in stats_df.columns if "percent" in c or "pct" in c or "%" in c]
    for c in percentage_columns:
        stats_df = stats_df.withColumn(c, clean_percentage_expr(c))

    # Rules
    if "age" in stats_df.columns:
        stats_df = stats_df.filter((col("age") >= 15) & (col("age") <= 23))
    if "minutes" in stats_df.columns:
        stats_df = stats_df.filter(col("minutes") >= 900)

    # Per 90 metrics
    if "minutes" in stats_df.columns:
        per90_features = ["goals", "assists", "xg", "xa", "shots", "key_passes"]
        for c in per90_features:
            if c in stats_df.columns:
                stats_df = stats_df.withColumn(f"{c}_per90", (col(c) / col("minutes")) * 90.0)

    # Deduplicate
    subset_cols = [c for c in ["player", "player_name", "season", "club", "team"] if c in stats_df.columns]
    if subset_cols:
        stats_df = stats_df.dropDuplicates(subset_cols)
    else:
        stats_df = stats_df.dropDuplicates()

    stats_df = stats_df.withColumn("trusted_load_date", current_date())

    # Write to MinIO
    print(f"Writing stats to {trusted_stats_out}")
    stats_df.write.mode("overwrite").parquet(trusted_stats_out)

    print("PySpark Data Cleaning completed successfully.")
    spark.stop()

if __name__ == "__main__":
    main()
