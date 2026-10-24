"""
download_fbref.py
=================

PURPOSE
-------
Downloads the four FBref pages of ONE league (Standard, Shooting, Playing
Time, Miscellaneous) with a real browser, and saves them for parse_fbref.py:

    data/raw/html/eng-premier-league/eng-premier-league_2627_standard.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_shooting.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_playing_time.html
    data/raw/html/eng-premier-league/eng-premier-league_2627_misc.html

"2627" is the season (2026-27), worked out from today's date. Each run
replaces the previous files of the same season: FBref's tables are
season-to-date totals, so the newest download always contains everything.

HOW TO RUN (from the repository's top folder)
----------
    python scraping/fbref/download_fbref.py eng-premier-league

    Leagues: eng-premier-league, esp-la-liga, fra-ligue-1,
             ger-bundesliga, ita-serie-a

    On the Linux VM, inside the virtual screen:
    xvfb-run -a python scraping/fbref/download_fbref.py eng-premier-league

Optional:
    --out-dir PATH    base folder (default: data/raw/html at the repository top)

The command ends with exit code 0 on success and 1 on failure. Airflow uses
that code to mark the task green or red.

RULES THIS SCRIPT FOLLOWS
-------------------------
- FBref allows at most 10 requests per minute (or blocks the IP for up to a
  day). We wait 15 seconds between pages, so 4 pages take about a minute.
  Run leagues one after another, never at the same time.
- A file is only saved if it really contains the player table. A page that
  failed is retried once, after a longer pause.
- Files are written under a temporary name and renamed at the end, so a crash
  halfway through never leaves a half-written file behind (the previous
  week's file stays in place instead).
"""

import argparse
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------

# league folder name -> (FBref competition number, name used in the URL)
LEAGUES = {
    "eng-premier-league": (9,  "Premier-League-Stats"),
    "esp-la-liga":        (12, "La-Liga-Stats"),
    "fra-ligue-1":        (13, "Ligue-1-Stats"),
    "ger-bundesliga":     (20, "Bundesliga-Stats"),
    "ita-serie-a":        (11, "Serie-A-M-Stats"),
}

# page -> (part of the URL, id of the player table on that page)
PAGES = {
    "standard":     ("stats",       "stats_standard"),
    "shooting":     ("shooting",    "stats_shooting"),
    "playing_time": ("playingtime", "stats_playing_time"),
    "misc":         ("misc",        "stats_misc"),
}

# The repository's top folder: this file is in scraping/fbref/, two levels down.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "raw" / "html"

PAUSE_SECONDS = 15          # between pages
RETRY_PAUSE_SECONDS = 60    # before retrying a failed page
CHALLENGE_TIMEOUT = 30      # max seconds for Cloudflare's check to clear
TABLE_TIMEOUT = 20          # max seconds for the player table to appear
CHROME_VERSION = None       # only set if you get a Chrome version error


def season_code(on_date):
    """European seasons run August-May. From July onwards we're in the season
    starting this year. e.g. 2026-10-21 -> "2627"; 2027-03-01 -> "2627"."""
    start = on_date.year if on_date.month >= 7 else on_date.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


# ---------------------------------------------------------------------------
# 2. STARTING THE BROWSER
# ---------------------------------------------------------------------------

def linux_browser_paths():
    """On a Linux server with Chromium + chromium-driver installed from apt
    (needed on ARM processors), point undetected-chromedriver at them.
    On Windows it finds Chrome and the driver by itself, so return nothing.

    undetected-chromedriver modifies the chromedriver file to hide it from
    Cloudflare. The system copy in /usr/bin can't be modified by a normal
    user, so we use our own copy, refreshed on every run so it always
    matches Chromium after system updates."""
    if not sys.platform.startswith("linux"):
        return {}
    browser = shutil.which("chromium")
    driver = shutil.which("chromedriver")
    if not (browser and driver):
        return {}
    our_copy = Path.home() / ".local" / "share" / "xvalue" / "chromedriver"
    our_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(driver, our_copy)
    return {"browser_executable_path": browser,
            "driver_executable_path": str(our_copy)}


def start_browser():
    options = uc.ChromeOptions()
    if sys.platform.startswith("linux"):
        options.add_argument("--no-sandbox")             # needed when running as root
        options.add_argument("--disable-dev-shm-usage")  # servers have little shared memory
        options.add_argument("--window-size=1920,1080")  # a normal desktop size
    # headless=False: a visible window (inside Xvfb on the VM). Cloudflare
    # detects invisible "headless" browsers much more easily.
    return uc.Chrome(options=options, version_main=CHROME_VERSION,
                     headless=False, **linux_browser_paths())


def close_browser(driver):
    try:
        driver.quit()
    except OSError:
        pass
    # undetected-chromedriver tries to close Chrome a second time when Python
    # exits, which prints a harmless but alarming error on Windows
    # ("WinError 6"). This switches that second attempt off.
    uc.Chrome.__del__ = lambda self: None


# ---------------------------------------------------------------------------
# 3. DOWNLOADING ONE PAGE
# ---------------------------------------------------------------------------

def is_cloudflare_page(html):
    signs = ["Just a moment...", "cf-chl", "challenge-platform", "Attention Required"]
    return any(sign in html for sign in signs)


def fetch_page(driver, url, table_id):
    """Open the page and return its HTML once the player table is there.
    Raises RuntimeError if Cloudflare blocks us or the table never appears."""
    driver.get(url)

    # 1) Wait for Cloudflare's check (if shown) to clear.
    waited = 0
    while is_cloudflare_page(driver.page_source):
        if waited >= CHALLENGE_TIMEOUT:
            raise RuntimeError("blocked by Cloudflare")
        time.sleep(1)
        waited += 1

    # 2) Wait until the player table exists in the page. This is better than
    # sleeping a fixed time: we continue as soon as it's ready.
    try:
        WebDriverWait(driver, TABLE_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, table_id)))
    except Exception:
        raise RuntimeError(f"table '{table_id}' did not appear")

    time.sleep(2)   # small margin so the rest of the page settles
    return driver.page_source


def save(html, path):
    """Write to 'name.html.tmp' first, then rename. Renaming is instant, so
    the final file is either complete or not touched at all."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 4. DOWNLOADING ONE LEAGUE
# ---------------------------------------------------------------------------

def download_league(league, out_dir, season):
    """Download the four pages of a league into out_dir/<league>/.
    Returns the list of pages that failed (empty list = success)."""
    comp_id, url_name = LEAGUES[league]
    league_folder = Path(out_dir) / league
    league_folder.mkdir(parents=True, exist_ok=True)
    failed = []

    driver = start_browser()
    try:
        for i, (page, (url_part, table_id)) in enumerate(PAGES.items()):
            if i > 0:
                time.sleep(PAUSE_SECONDS)
            url = f"https://fbref.com/en/comps/{comp_id}/{url_part}/{url_name}"
            out_file = league_folder / f"{league}_{season}_{page}.html"
            print(f"{page}: {url}")

            for attempt in (1, 2):
                try:
                    html = fetch_page(driver, url, table_id)
                    save(html, out_file)
                    print(f"   OK, {len(html):,} characters -> {out_file}")
                    break
                except RuntimeError as error:
                    print(f"   attempt {attempt} failed: {error}")
                    if attempt == 1:
                        print(f"   waiting {RETRY_PAUSE_SECONDS} s before retrying...")
                        time.sleep(RETRY_PAUSE_SECONDS)
                    else:
                        failed.append(page)
    finally:
        close_browser(driver)   # always close Chrome, even after a crash

    return failed


# ---------------------------------------------------------------------------
# 5. COMMAND LINE
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Download the FBref pages of one league.")
    parser.add_argument("league", choices=LEAGUES, help="which league to download")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                        help="base folder for the HTML files")
    args = parser.parse_args()

    season = season_code(date.today())
    print(f"Downloading {args.league}, season {season}, into "
          f"{Path(args.out_dir) / args.league}\n")

    failed = download_league(args.league, args.out_dir, season)

    if failed:
        print(f"\nFAILED pages: {', '.join(failed)}")
        sys.exit(1)
    print(f"\nAll {len(PAGES)} pages downloaded.")


if __name__ == "__main__":
    main()