# xValue

Final Master's Project for UPC Data Science and Engineering. A way to give football players an objective value.

---

## Project Structure

```
xValue/
├── data/
│   ├── raw/          # Downloaded data (gitignored — stored in MinIO)
│   └── processed/    # Cleaned/merged data (gitignored — stored in MinIO)
├── etl/              # Scripts to download and upload data
│   ├── download_stats.py   # Fetches player stats from FBref
│   ├── download_u23.py     # Fetches U23 player data
│   └── minio_client.py     # Reusable MinIO/S3 upload-download helper
├── models/           # Trained model artefacts
├── notebooks/        # Exploratory analysis
├── reports/          # Figures and outputs
├── xValue/           # Core Python module
├── docker-compose.yml
├── requirements.txt
└── .env.example      # Template for required environment variables
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

| Variable | Description |
|---|---|
| `MINIO_ROOT_USER` | Admin username for MinIO |
| `MINIO_ROOT_PASSWORD` | Admin password (min. 8 characters) |
| `MINIO_ENDPOINT` | MinIO API URL (default: `http://localhost:9000`) |
| `MINIO_BUCKET` | Bucket name where data files are stored |

### 2. Start MinIO

```bash
docker compose --env-file .env.local up -d
```

This starts two containers:
- **`xvalue-minio`** — the MinIO server (S3 API on port `9000`, web console on port `9001`)
- **`xvalue-minio-init`** — a one-shot container that creates the bucket automatically

Once running, the web console is available at **http://localhost:9001**.

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

## Setup

Install Python dependencies into your virtual environment:

```bash
pip install -r requirements.txt
```

### Run ETL scripts

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
    ├──▶ docker compose reads it → starts MinIO on localhost:9000
    │
    └──▶ python-dotenv reads it → minio_client.py connects to localhost:9000
                                        │
                          etl/download_stats.py
                                        │
                          ┌─────────────┴──────────────┐
                          ▼                            ▼
                   data/raw/*.csv              MinIO bucket
                   (local cache)               (shared store)
```
