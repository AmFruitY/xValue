"""Convert raw CSV files to Parquet format in the interim data folder.

Walks every subdirectory inside ``data/raw/`` (excluding ``test/``) and
converts each ``.csv`` file to a ``.parquet`` file, mirroring the same
folder structure under ``data/interim/``.

Usage (from the project root):
    python -m etl.processing.csv_to_parquet

Optional arguments:
    --raw-dir      Path to the raw data folder  (default: data/raw)
    --interim-dir  Path to the interim data folder (default: data/interim)
    --exclude      Subfolder names to skip (default: test)
    --verbose      Print extra information while running
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------

def convert_csv_to_parquet(
    raw_dir: Path,
    interim_dir: Path,
    exclude: set[str],
) -> tuple[int, int]:
    """Recursively convert CSV files from *raw_dir* to Parquet in *interim_dir*.

    Parameters
    ----------
    raw_dir:
        Root of the raw data folder (e.g. ``data/raw``).
    interim_dir:
        Root of the interim data folder (e.g. ``data/interim``).
    exclude:
        Set of *top-level* subfolder names to skip (e.g. ``{"test"}``).

    Returns
    -------
    (converted, skipped)
        Number of files successfully converted and number of files skipped due
        to errors.
    """
    converted = 0
    skipped = 0

    csv_files = sorted(raw_dir.rglob("*.csv"))

    if not csv_files:
        log.warning("No CSV files found under '%s'.", raw_dir)
        return converted, skipped

    for csv_path in csv_files:
        # Compute the path relative to raw_dir so we can mirror it
        relative = csv_path.relative_to(raw_dir)

        # Skip if the *first* component of the relative path is in exclude list
        top_level = relative.parts[0]
        if top_level in exclude:
            log.debug("Skipping '%s' (excluded folder: %s).", csv_path, top_level)
            continue

        # Build the destination parquet path
        parquet_relative = relative.with_suffix(".parquet")
        parquet_path = interim_dir / parquet_relative

        # Create parent directories if needed
        parquet_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            df = pd.read_csv(csv_path, low_memory=False)
            df.to_parquet(parquet_path, index=False, engine="pyarrow")
            log.info("✓  %s  →  %s  (%d rows, %d cols)",
                     relative, parquet_relative, len(df), len(df.columns))
            converted += 1
        except Exception as exc:  # noqa: BLE001
            log.error("✗  Failed to convert '%s': %s", csv_path, exc)
            skipped += 1

    return converted, skipped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert raw CSV files to Parquet in the interim folder.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Root raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--interim-dir",
        type=Path,
        default=Path("data/interim"),
        help="Root interim data directory (default: data/interim)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["test"],
        metavar="FOLDER",
        help="Top-level subfolders to exclude (default: test)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    raw_dir: Path = args.raw_dir
    interim_dir: Path = args.interim_dir
    exclude: set[str] = set(args.exclude)

    if not raw_dir.exists():
        log.error("Raw directory '%s' does not exist.", raw_dir)
        raise SystemExit(1)

    interim_dir.mkdir(parents=True, exist_ok=True)

    log.info("Raw dir    : %s", raw_dir.resolve())
    log.info("Interim dir: %s", interim_dir.resolve())
    log.info("Excluding  : %s", exclude)
    log.info("─" * 60)

    converted, skipped = convert_csv_to_parquet(raw_dir, interim_dir, exclude)

    log.info("─" * 60)
    log.info("Done. Converted: %d  |  Skipped (errors): %d", converted, skipped)


if __name__ == "__main__":
    main()
