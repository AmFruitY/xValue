# xValue

Final Master's Project for UPC Data Science and Engineering. A way to give football players an objective value.

---

## Project Structure

```
xValue/
├── dags/
│   └── xvalue_pipeline.py  # Airflow DAG (schedules ETL runs)
├── data/
│   ├── raw/          # Downloaded data (gitignored — stored in MinIO)
│   └── processed/    # Cleaned/merged data (gitignored — stored in MinIO)
├── etl/              # Scripts to download, clean, and upload data
│   ├── download_stats.py          # Fetches all-age player stats from FBref
│   ├── download_u23.py            # Fetches U23 player stats from FBref
│   ├── join_players.py            # Joins FBref stats with Transfermarkt bios
│   ├── extract_player_market_value.py  # Extracts market value subset
│   ├── limpieza_datos.py          # Cleans landing zone data into trusted zone
│   ├── exploitation_zone.py       # Builds feature tables for modelling
│   └── minio_client.py            # Reusable MinIO/S3 upload-download helper
├── models/           # Trained model artefacts
├── notebooks/        # Exploratory analysis
├── reports/          # Figures and outputs
├── xValue/           # Core Python module
├── Dockerfile.airflow  # Custom Airflow image with project dependencies
├── docker-compose.yml
├── requirements.txt
└── .env.example        # Template for required environment variables
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
download_stats ──┬──▶ join_players    ──▶ extract_market_value
               │
dowload_u23  ──┼──▶ limpieza_datos  ──▶ exploitation_zone
               ┘
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
            ├──▶ download_stats.py  → data/raw/  + MinIO upload
            ├──▶ download_u23.py   → data/raw/
            ├──▶ join_players.py   → data/processed/
            ├──▶ limpieza_datos.py → data/trusted/
            ├──▶ extract_market_value.py → data/processed/
            └──▶ exploitation_zone.py    → data/exploitation/
```
