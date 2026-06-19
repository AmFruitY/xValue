import pandas as pd
import duckdb
from pathlib import Path
import re


# =========================
# CONFIGURACIÓN
# =========================

LANDING_PATH = Path("data/landing")
TRUSTED_PATH = Path("data/trusted")

INJURIES_FILE = LANDING_PATH / "injuries" / "raw_injuries.csv"
STATS_FILE = LANDING_PATH / "player_stats" / "raw_u23_player_stats.csv"

TRUSTED_DB = TRUSTED_PATH / "football_trusted.duckdb"

TRUSTED_PATH.mkdir(parents=True, exist_ok=True)


# =========================
# FUNCIONES GENERALES
# =========================

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace(r"[^a-zA-Z0-9_]", "", regex=True)
    )
    return df


def normalize_text(value):
    if pd.isna(value):
        return None
    return str(value).strip()


def clean_money(value):
    """
    Convierte valores tipo '€1.5m', '€750k', '1.2M' a número en euros.
    """
    if pd.isna(value):
        return None

    value = str(value).lower().replace("€", "").replace(",", "").strip()

    multiplier = 1

    if "m" in value:
        multiplier = 1_000_000
        value = value.replace("m", "")
    elif "k" in value:
        multiplier = 1_000
        value = value.replace("k", "")

    value = re.sub(r"[^0-9.]", "", value)

    if value == "":
        return None

    return float(value) * multiplier


def clean_percentage(value):
    if pd.isna(value):
        return None

    value = str(value).replace("%", "").strip()

    try:
        return float(value) / 100
    except ValueError:
        return None


# =========================
# LIMPIEZA DATASET LESIONES
# =========================

def clean_injuries(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = clean_column_names(df)

    # Normalización textual
    text_columns = [
        "player_name", "player", "club", "team",
        "injury", "injury_type", "season", "position"
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(normalize_text)

    # Fechas
    date_columns = ["injury_start", "injury_end", "from", "until", "date"]

    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Días lesionado
    possible_days_cols = ["days_out", "days", "duration", "days_injured"]

    for col in possible_days_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.extract(r"(\d+)")
                .astype(float)
            )

    # Si existen fechas pero no días lesionado, se calcula
    if "injury_start" in df.columns and "injury_end" in df.columns:
        if "days_out" not in df.columns:
            df["days_out"] = (df["injury_end"] - df["injury_start"]).dt.days

    # Reglas de negocio
    if "days_out" in df.columns:
        df = df[df["days_out"].isna() | (df["days_out"] >= 0)]

    # Eliminar duplicados
    subset_cols = [col for col in ["player_name", "injury_start", "injury_type", "days_out"] if col in df.columns]

    if subset_cols:
        df = df.drop_duplicates(subset=subset_cols)
    else:
        df = df.drop_duplicates()

    # Añadir metadata
    df["trusted_load_date"] = pd.Timestamp.today().normalize()

    return df


# =========================
# LIMPIEZA DATASET ESTADÍSTICAS SUB-23
# =========================

def clean_player_stats(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = clean_column_names(df)

    # Normalización textual
    text_columns = [
        "player", "player_name", "squad", "team",
        "club", "nation", "position", "league", "season"
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(normalize_text)

    # Conversión numérica
    numeric_columns = [
        "age", "minutes", "mins", "starts", "matches",
        "goals", "assists", "xg", "xa", "shots",
        "key_passes", "progressive_carries",
        "progressive_passes", "progressive_actions",
        "yellow_cards", "red_cards",
        "market_value", "salary"
    ]

    for col in numeric_columns:
        if col in df.columns:
            if col in ["market_value", "salary"]:
                df[col] = df[col].apply(clean_money)
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalizar columnas de porcentaje si existen
    percentage_columns = [col for col in df.columns if "percent" in col or "pct" in col or "%" in col]

    for col in percentage_columns:
        df[col] = df[col].apply(clean_percentage)

    # Unificar minutos
    if "mins" in df.columns and "minutes" not in df.columns:
        df = df.rename(columns={"mins": "minutes"})

    # Reglas de negocio
    if "age" in df.columns:
        df = df[df["age"].between(15, 23, inclusive="both")]

    if "minutes" in df.columns:
        df = df[df["minutes"] >= 900]

    # Crear métricas por 90
    if "minutes" in df.columns:
        per90_features = ["goals", "assists", "xg", "xa", "shots", "key_passes"]

        for col in per90_features:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] / df["minutes"] * 90

    # Eliminar duplicados
    subset_cols = [col for col in ["player", "player_name", "season", "club", "team"] if col in df.columns]

    if subset_cols:
        df = df.drop_duplicates(subset=subset_cols)
    else:
        df = df.drop_duplicates()

    # Añadir metadata
    df["trusted_load_date"] = pd.Timestamp.today().normalize()

    return df


# =========================
# GUARDADO EN TRUSTED ZONE
# =========================

def save_to_trusted_duckdb(injuries_df: pd.DataFrame, stats_df: pd.DataFrame):
    con = duckdb.connect(str(TRUSTED_DB))

    con.execute("CREATE OR REPLACE TABLE trusted_injuries AS SELECT * FROM injuries_df")
    con.execute("CREATE OR REPLACE TABLE trusted_u23_player_stats AS SELECT * FROM stats_df")

    con.close()


def save_to_parquet(injuries_df: pd.DataFrame, stats_df: pd.DataFrame):
    injuries_df.to_parquet(TRUSTED_PATH / "trusted_injuries.parquet", index=False)
    stats_df.to_parquet(TRUSTED_PATH / "trusted_u23_player_stats.parquet", index=False)


# =========================
# MAIN PIPELINE
# =========================

def main():
    print("Leyendo y limpiando dataset de lesiones...")
    injuries_df = clean_injuries(INJURIES_FILE)

    print("Leyendo y limpiando dataset de estadísticas sub-23...")
    stats_df = clean_player_stats(STATS_FILE)

    print("Guardando datos en Trusted Zone...")
    save_to_trusted_duckdb(injuries_df, stats_df)
    save_to_parquet(injuries_df, stats_df)

    print("Proceso completado correctamente.")
    print(f"Lesiones limpias: {len(injuries_df)} registros")
    print(f"Estadísticas sub-23 limpias: {len(stats_df)} registros")
    print(f"Base DuckDB creada en: {TRUSTED_DB}")


if __name__ == "__main__":
    main()