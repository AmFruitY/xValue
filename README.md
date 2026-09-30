# xValue

Final Master's Project for UPC Data Science and Engineering. A way to give football players an objective value.

---

## Project Structure

```
xValue/
├── dags/
│   ├── upload_landing_dag.py      # Airflow DAG for landing zone uploads
│   └── xvalue_pipeline.py         # Airflow DAG (schedules full ETL runs)
├── data/
│   ├── raw/          # Downloaded data (gitignored — stored in MinIO)
│   └── processed/    # Cleaned/merged data (gitignored — stored in MinIO)
├── etl/              # ETL pipeline — organized into subpackages
│   ├── extract/      # Data extraction from external sources
│   │   ├── download_u23.py                  # Fetches U23 player stats from FBref
│   │   ├── fbref_stats_all_players.py       # Fetches all-age player stats from FBref
│   │   ├── statsbomb_stats_all_players.py   # Fetches stats from StatsBomb
│   │   └── understat_stats_all_players.py   # Fetches stats from Understat
│   ├── processing/   # Data cleaning and transformation
│   │   ├── exploitation_zone.py             # Builds feature tables for modelling
│   │   ├── extract_player_market_value.py   # Extracts market value subset
│   │   ├── join_players.py                  # Joins FBref stats with Transfermarkt bios
│   │   ├── limpieza_datos.py                # Cleans landing zone data into trusted zone
│   │   └── limpieza_spark.py                # PySpark cleaning into Parquet (trusted zone)
│   ├── shared/       # Shared utilities
│   │   └── minio_client.py                  # Reusable MinIO/S3 upload-download helper
│   └── upload/       # Data upload to storage
│       ├── csv_to_parquet_landing.py        # Converts CSVs to Parquet for landing zone
│       └── upload_landing.py                # Uploads raw files to MinIO landing zone
├── models/           # Trained model artefacts
│   ├── xvalue_xgb.joblib  # Serialised XGBoost pipeline
│   └── README.md          # Model card (hyperparameters, evaluation, intended use)
├── notebooks/        # Exploratory analysis
├── references/       # External references and literature
├── reports/
│   └── figures/      # Generated plots and output figures
├── test/             # Ad-hoc scripts and data used during development
├── xValue/           # Core Python package
│   ├── config.py          # Project-wide configuration
│   ├── dataset.py         # Dataset loading and preparation
│   ├── features.py        # Feature engineering utilities
│   ├── plots.py           # Plotting helpers
│   └── modeling/
│       ├── train.py       # Model training entry-point
│       └── predict.py     # Inference / prediction entry-point
├── Dockerfile.airflow     # Custom Airflow image with project dependencies
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example           # Template for required environment variables
```

---

## Local Data Store — MinIO

Large data files are **not committed to Git**. Instead, they are stored in a local
[MinIO](https://min.io/) instance — an S3-compatible object store that runs in Docker.
This means anyone working on the project can pull and push data files to a shared location.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running

### 1. Set up credentials

Copy the example env file and fill in your own values:

```bash
cp .env.example .env.local
```

`.env.local` is never committed to Git. The variables it must contain are:

**MinIO**

| Variable | Description |
|---|---|
| `MINIO_ROOT_USER` | Admin username for MinIO |
| `MINIO_ROOT_PASSWORD` | Admin password (min. 8 characters) |
| `MINIO_ENDPOINT` | MinIO API URL (default: `http://localhost:9000`) |
| `MINIO_BUCKET` | Bucket name where data files are stored |

**Airflow**

| Variable | Description |
|---|---|
| `AIRFLOW__CORE__FERNET_KEY` | Encryption key — generate with the command below |
| `AIRFLOW_WWW_USER_PASSWORD` | Password for the Airflow web UI admin account |
| `POSTGRES_PASSWORD` | Password for the internal Airflow metadata database |

Generate a Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Start MinIO

```bash
docker compose --env-file .env.local up -d
```

This starts all containers:
- **`xvalue-minio`** — MinIO server (S3 API on port `9000`, web console on port `9001`)
- **`xvalue-minio-init`** — one-shot container that creates the bucket
- **`xvalue-postgres`** — PostgreSQL database used by Airflow internally
- **`xvalue-airflow-init`** — one-shot container that sets up the Airflow DB and admin user
- **`xvalue-airflow-webserver`** — Airflow web UI on port `8080`
- **`xvalue-airflow-scheduler`** — background process that triggers scheduled DAG runs

| Service | URL |
|---|---|
| MinIO web console | http://localhost:9001 |
| Airflow web UI | http://localhost:8080 |

Log in to Airflow with username `admin` and the `AIRFLOW_WWW_USER_PASSWORD` from your `.env.local`.

### 3. Stop MinIO

```bash
# Stop containers (data is preserved)
docker compose --env-file .env.local down

# Stop and delete all stored data (full reset)
docker compose --env-file .env.local down -v
```

### Using MinIO in Python

The `etl/minio_client.py` helper provides a pre-configured connection to MinIO.
It reads credentials from `.env.local` automatically — no setup needed in your scripts.

```python
from etl.minio_client import upload_file, download_file, list_objects

# Upload a local file to MinIO
upload_file("data/raw/all_players.csv", "raw/all_players.csv")

# Download a file from MinIO
download_file("raw/all_players.csv", "data/raw/all_players.csv")

# List all files in the bucket
files = list_objects(prefix="raw/")
```

---

## Airflow — Scheduled ETL

Airflow automatically runs the full ETL pipeline every Monday at midnight.
You can also trigger it manually at any time from the web UI.

### Pipeline graph

```
upload_landing ──┐
download_stats ──┼──▶ join_players    ──▶ extract_market_value
                 │
dowload_u23    ──┴──▶ limpieza_spark  ──▶ exploitation_zone
```

### Manually trigger a run

1. Open **http://localhost:8080** and log in
2. Find `xvalue_etl_pipeline` in the DAG list
3. Click the **▶ Trigger DAG** button on the right

---

## Setup

Install Python dependencies into your virtual environment:

```bash
pip install -r requirements.txt
```

### Run ETL scripts manually (without Airflow)

```bash
# Download player stats from FBref and upload to MinIO
python -m etl.download_stats

# Download U23 player data
python -m etl.download_u23
```

---

## How it all connects

```
.env.local
    │
    ├──▶ docker compose → MinIO (port 9000) + Airflow (port 8080)
    │
    └──▶ python-dotenv → minio_client.py connects to MinIO

Airflow scheduler (weekly)
    └──▶ triggers xvalue_etl_pipeline DAG
            ├──▶ upload_landing.py   → MinIO (landing zone)
            ├──▶ download_stats.py   → MinIO (raw zone)
            ├──▶ download_u23.py     → MinIO (raw zone)
            ├──▶ join_players.py     → MinIO (processed zone)
            ├──▶ limpieza_spark.py   → PySpark reads landing/raw → writes Parquet to MinIO (trusted zone)
            ├──▶ extract_market_value.py → MinIO (processed zone)
            └──▶ exploitation_zone.py    → DuckDB reads Parquet from MinIO → writes to MinIO (exploitation zone)
```

---

## 🏛️ Lakehouse Architecture

This project implements a modern data lakehouse pattern locally using **MinIO** as the storage layer, **Apache Spark (PySpark)** as the distributed data processing engine, and **DuckDB** as the analytical engine.

1. **Landing / Raw Zone**: Python scripts fetch data from APIs and save raw CSVs into MinIO.
2. **Trusted Zone**: PySpark (`limpieza_spark.py`) reads the raw CSVs directly from MinIO, cleans the data using distributed DataFrame operations, and writes optimized Parquet files back to MinIO.
3. **Exploitation Zone**: DuckDB (`exploitation_zone.py`) connects to MinIO via the `httpfs` extension to query the trusted Parquet files instantly without downloading them, and builds the final analytical tables.

## 🤖 Modelling

The exploitation-zone tables feed an XGBoost regressor that estimates a player's
transfer fee from accumulated performance stats, profile and injury history.

- **Target:** `log1p(fee)` (only transfers with `fee > 0`)
- **Features:** season stats (`avg_*_acum`), age, injury features
  (`total_days_out`, `n_injury_records`, `worst_injury_days`, ...) and categorical
  variables (`league`, `club`, `window`, `nationality`, `position`)
- **Training:** `RandomizedSearchCV` (60 iterations, 3-fold CV), sample weights
  proportional to `log1p(fee)` to reduce underestimation of expensive transfers
- **Split:** 80/20 random, seed 42

### Results (test set)

| Scale | RMSE | MAE | R² |
|---|---|---|---|
| Log | 1.0262 | 0.7422 | 0.5377 |
| Euros | 6,661,431.81 | 3,255,870.18 | 0.6089 |

### Reproduce

```bash
# ============================================================
# XGBOOST - RANDOMIZED SEARCH 2
# Búsqueda concentrada alrededor de los mejores parámetros
# Target: log1p(fee)
# ============================================================


# ============================================================
# 1. IMPORTS
# ============================================================

import numpy as np
import pandas as pd

from xgboost import XGBRegressor

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from sklearn.model_selection import RandomizedSearchCV


# ============================================================
# 2. VARIABLES
# ============================================================


#VARS ELIMINADAS: 'player_id','avg_Min_acum','avg_90s_acum','avg_G-PK_1_acum', 'avg_PKatt_acum', 'avg_Min%_acum'
cols_numericas = [
    'season', 'age', 'avg_MP_acum', 'avg_Starts_acum',  'avg_Gls_acum', 'avg_Ast_acum', 'avg_G+A_acum',
    'avg_G-PK_acum', 'avg_PK_acum', 'avg_PK_perc_acum', 'avg_CrdY_acum',
    'avg_CrdR_acum', 'avg_Gls_1_acum', 'avg_Ast_1_acum', 'avg_G+A_1_acum',
     'avg_G+A-PK_acum', 'avg_Sh_acum', 'avg_SoT_acum',
    'avg_SoT%_acum', 'avg_Sh/90_acum', 'avg_SoT/90_acum', 'avg_G/Sh_acum',
    'avg_G/SoT_acum', 'avg_Mn/MP_acum', 'avg_Mn/Start_acum',
    'avg_Compl_acum', 'avg_Subs_acum', 'avg_Mn/Sub_acum', 'avg_unSub_acum',
    'avg_PPM_acum', 'avg_onG_acum', 'avg_onGA_acum', 'avg_+/-_acum',
    'avg_+/-90_acum', 'avg_On-Off_acum', 'avg_2CrdY_acum', 'avg_Fls_acum',
    'avg_Fld_acum', 'avg_Off_acum', 'avg_Crs_acum', 'avg_Int_acum',
    'avg_TklW_acum', 'avg_PKwon_acum', 'avg_PKcon_acum', 'avg_OG_acum',
    'num_equipos_acum', 'total_days_out', 'total_games_missed',
    'n_distinct_injuries', 'n_injury_records', 'max_same_injury_repeats',
    'has_recurrent_injury', 'age_at_last_injury', 'age_at_first_injury',
    'worst_injury_days'
]

cols_categoricas = [
    'league',
    'club',
    'window',
    'nationality',
    'position'
]

target = "fee"


# ============================================================
# 3. CREAR DATASET
# ============================================================

cols_modelo = cols_numericas + cols_categoricas + [target, "player_name"]

df_pd = (
    df_xvalue
    .select(cols_modelo)
    .filter("fee IS NOT NULL")
    .filter("fee > 0")
    .toPandas()
)

# Reemplazar infinitos por NaN
df_pd[cols_numericas] = (
    df_pd[cols_numericas]
    .replace([np.inf, -np.inf], np.nan)
)


# ============================================================
# 4. TRAIN / TEST
# ============================================================

# IMPORTANTE:
# Utilizamos exactamente el mismo split que en la búsqueda anterior.

rng = np.random.default_rng(42)

mask_train = rng.random(len(df_pd)) < 0.80

df_train = df_pd.loc[mask_train].copy()
df_test = df_pd.loc[~mask_train].copy()


# ============================================================
# 5. X / Y
# ============================================================

X_train = df_train[
    cols_numericas + cols_categoricas
]

X_test = df_test[
    cols_numericas + cols_categoricas
]

y_train = df_train[target]
y_test = df_test[target]

# Target logarítmico
y_train_log = np.log1p(y_train)
y_test_log = np.log1p(y_test)


# ============================================================
# 5b. SAMPLE WEIGHTS  <-- NUEVO
# ============================================================
# El análisis de residuos mostró sesgo sistemático (subestimación)
# en los fichajes caros: P95-P99 y P99-P100 concentran ~67% del
# error cuadrático total con menos del 5% de los casos.
# Damos más peso a esos casos usando el propio fee como peso.
#
# Se prueban variantes suaves para no sobrecorregir hacia arriba
# (podrías experimentar con log1p(fee) si el peso lineal resulta
# demasiado agresivo).

sample_weight_train = np.log1p(y_train.to_numpy())
sample_weight_train = sample_weight_train / sample_weight_train.mean()


# ============================================================
# 6. PREPROCESSING
# ============================================================

numeric_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="median"))
])

categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    (
        "onehot",
        OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=True
        )
    )
])

preprocessor = ColumnTransformer([
    (
        "num",
        numeric_transformer,
        cols_numericas
    ),
    (
        "cat",
        categorical_transformer,
        cols_categoricas
    )
])


# ============================================================
# 7. MODELO BASE
# ============================================================

xgb = XGBRegressor(
    objective="reg:squarederror",

    n_estimators=1250,
    learning_rate=0.08,
    max_depth=4,
    min_child_weight=10,
    subsample=0.9,
    colsample_bytree=0.6,
    reg_alpha=1.0,
    reg_lambda=3,

    n_jobs=4,
    random_state=42
)


# ============================================================
# 8. PIPELINE
# ============================================================

pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", xgb)
])


# ============================================================
# 9. NUEVO ESPACIO DE BÚSQUEDA
# ============================================================

param_distributions = {

    # Complejidad del árbol
    "model__max_depth": [
        3,
        4,
        5
    ],

    # Learning rate
    "model__learning_rate": [
        0.05,
        0.07,
        0.08,
        0.10
    ],

    # Número de árboles
    "model__n_estimators": [
        1000,
        1250,
        1500,
        1750
    ],

    # Regularización de las hojas
    "model__min_child_weight": [
        7,
        10,
        15
    ],

    # Subsampling
    "model__subsample": [
        0.8,
        0.9,
        1.0
    ],

    # Variables utilizadas por árbol
    "model__colsample_bytree": [
        0.5,
        0.6,
        0.7
    ],

    # Regularización L1
    "model__reg_alpha": [
        0.5,
        1.0,
        1.5,
        2.0
    ],

    # Regularización L2
    "model__reg_lambda": [
        2,
        3,
        5
    ]
}


# ============================================================
# 10. RANDOMIZED SEARCH
# ============================================================

random_search_2 = RandomizedSearchCV(
    estimator=pipeline,

    param_distributions=param_distributions,

    # Más iteraciones porque ahora el espacio está concentrado
    n_iter=60,

    # CV únicamente sobre TRAIN
    cv=3,

    # Optimizar RMSE sobre log(fee)
    scoring="neg_root_mean_squared_error",

    verbose=2,

    random_state=123,

    # Evitar saturar la máquina
    n_jobs=1,

    # Necesario para analizar train vs validation después
    return_train_score=True
)


# ============================================================
# 11. ENTRENAMIENTO
# ============================================================

print("\n" + "=" * 80)
print("INICIANDO RANDOMIZED SEARCH 2")
print("=" * 80)

print("\nConfiguración:")
print("  Iteraciones :", 60)
print("  CV          : 3 folds")
print("  Métrica     : RMSE Log")
print("  Target      : log1p(fee)")
print("  Sample weight: fee / fee.mean()  <-- NUEVO")

print("\nRangos:")
print("  max_depth        :", param_distributions["model__max_depth"])
print("  learning_rate    :", param_distributions["model__learning_rate"])
print("  n_estimators     :", param_distributions["model__n_estimators"])
print("  min_child_weight :", param_distributions["model__min_child_weight"])
print("  subsample        :", param_distributions["model__subsample"])
print("  colsample        :", param_distributions["model__colsample_bytree"])
print("  reg_alpha        :", param_distributions["model__reg_alpha"])
print("  reg_lambda       :", param_distributions["model__reg_lambda"])

print("\n" + "-" * 80)
print("El modelo anterior obtuvo:")
print("  RMSE Log = 0.9953")
print("  R² Log   = 0.5312")
print("-" * 80)

print("\nComenzando búsqueda...\n")


# ============================================================
# 12. FIT
# ============================================================

random_search_2.fit(
    X_train,
    y_train_log,
    model__sample_weight=sample_weight_train  # <-- NUEVO
)


# ============================================================
# 13. MEJORES PARÁMETROS
# ============================================================

print("\n" + "=" * 80)
print("MEJORES HIPERPARÁMETROS - SEARCH 2")
print("=" * 80)

print(
    f"\nMejor RMSE CV Log: "
    f"{-random_search_2.best_score_:.4f}"
)

print("\nParámetros:")

for param, value in random_search_2.best_params_.items():
    print(f"{param:<40} {value}")


# ============================================================
# 14. TOP 15 CONFIGURACIONES
# ============================================================

results_2 = pd.DataFrame(
    random_search_2.cv_results_
)

results_2["RMSE_CV_Log"] = (
    -results_2["mean_test_score"]
)

results_2["RMSE_Train_Log"] = (
    -results_2["mean_train_score"]
)

results_2 = results_2.sort_values(
    "RMSE_CV_Log",
    ascending=True
)


cols_resultado = [
    "RMSE_CV_Log",
    "RMSE_Train_Log",
    "param_model__max_depth",
    "param_model__learning_rate",
    "param_model__n_estimators",
    "param_model__min_child_weight",
    "param_model__subsample",
    "param_model__colsample_bytree",
    "param_model__reg_alpha",
    "param_model__reg_lambda"
]


print("\n" + "=" * 80)
print("TOP 15 CONFIGURACIONES")
print("=" * 80)

print(
    results_2[
        cols_resultado
    ]
    .head(15)
    .to_string(index=False)
)


# ============================================================
# 15. GUARDAR EL MEJOR MODELO EN MEMORIA
# ============================================================

best_model_2 = (
    random_search_2.best_estimator_
)


print("\n" + "=" * 80)
print("SEARCH 2 FINALIZADO")
print("=" * 80)

print(
    "\nEl modelo está guardado como:"
)

print("best_model_2")



# ============================================================
# 16. PREDICCIONES SOBRE TEST Y EXPORT A PARQUET
# ============================================================

# Predicción en escala log, revertida con expm1 para volver a euros
pred_test_log = best_model_2.predict(X_test)
pred_test = np.expm1(pred_test_log)

df_resultado = pd.DataFrame({
    "player_name": df_test["player_name"].values,
    "season" : df_test["season"].values,
    "fee": y_test.values,
    "prediction": pred_test
})

df_resultado.to_parquet(
    "test_predictions.parquet",
    index=False
)

print("\n" + "=" * 80)
print("PARQUET GUARDADO: test_predictions.parquet")
print("=" * 80)
print(df_resultado.head(10).to_string(index=False))
```

The trained model is saved in `models/`. Full details (hyperparameters, limitations,
intended use) are in the [model card](models/README.md).

### Evaluation against Transfermarkt

`xvalue_gap = |fee - prediction|` is compared with
`transfermarkt_gap = |market_value - prediction|`. 
