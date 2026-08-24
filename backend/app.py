"""
Starter/test backend for the student deploy pipeline.

On startup, creates a `teams` table (if it doesn't already exist) and seeds
it with the 32 NFL team names + helmet image URLs the first time it runs
against an empty table. Exposes that list over a small JSON API that the
frontend reads.

Reads its Postgres connection string from DATABASE_URL, which the deploy
pipeline injects automatically (see templates/env.template in the
studentapps repo) -- nothing here is hardcoded to a particular student_id,
host, or password.
"""

import os
import time

import psycopg2
from flask import Flask, jsonify

app = Flask(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]

# (name, ESPN team abbreviation). Helmet images are served from ESPN's
# public team-logo CDN rather than stored in this repo -- the frontend
# just points an <img> at HELMET_URL_TEMPLATE.format(abbr).
NFL_TEAMS = [
    ("Arizona Cardinals", "ari"), ("Atlanta Falcons", "atl"),
    ("Baltimore Ravens", "bal"), ("Buffalo Bills", "buf"),
    ("Carolina Panthers", "car"), ("Chicago Bears", "chi"),
    ("Cincinnati Bengals", "cin"), ("Cleveland Browns", "cle"),
    ("Dallas Cowboys", "dal"), ("Denver Broncos", "den"),
    ("Detroit Lions", "det"), ("Green Bay Packers", "gb"),
    ("Houston Texans", "hou"), ("Indianapolis Colts", "ind"),
    ("Jacksonville Jaguars", "jax"), ("Kansas City Chiefs", "kc"),
    ("Las Vegas Raiders", "lv"), ("Los Angeles Chargers", "lac"),
    ("Los Angeles Rams", "lar"), ("Miami Dolphins", "mia"),
    ("Minnesota Vikings", "min"), ("New England Patriots", "ne"),
    ("New Orleans Saints", "no"), ("New York Giants", "nyg"),
    ("New York Jets", "nyj"), ("Philadelphia Eagles", "phi"),
    ("Pittsburgh Steelers", "pit"), ("San Francisco 49ers", "sf"),
    ("Seattle Seahawks", "sea"), ("Tampa Bay Buccaneers", "tb"),
    ("Tennessee Titans", "ten"), ("Washington Commanders", "wsh"),
]

HELMET_URL_TEMPLATE = "https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db(retries: int = 10, delay_seconds: int = 2) -> None:
    """Creates + seeds the teams table, and migrates older databases that
    already have a `teams` table without a `helmet_url` column.

    CREATE TABLE IF NOT EXISTS only helps brand-new databases -- an
    existing `teams` table (e.g. from before this column existed) is left
    untouched by it, and the seed step below only ever runs once (when the
    table is empty), so it would never backfill existing rows either.
    That's why this explicitly ALTERs the table and backfills helmet_url
    for any row missing it, every time this runs; both statements are
    no-ops on a database that's already up to date, so this stays safe to
    call on every container start/redeploy.

    Retries briefly on connection failure in case the container starts
    slightly before Postgres is reachable on the network.
    """
    conn = None
    for attempt in range(1, retries + 1):
        try:
            conn = get_connection()
            break
        except psycopg2.OperationalError as exc:
            if attempt == retries:
                raise
            print(f"[init_db] Postgres not reachable yet (attempt {attempt}/{retries}): {exc}", flush=True)
            time.sleep(delay_seconds)

    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS teams (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    helmet_url TEXT
                )
                """
            )

            # Migration for tables created before helmet_url existed.
            cur.execute("ALTER TABLE teams ADD COLUMN IF NOT EXISTS helmet_url TEXT")

            # Backfill any row (old or newly created above) that's missing
            # its helmet_url -- e.g. the 32 rows seeded by a pre-migration
            # deploy.
            cur.executemany(
                """
                UPDATE teams SET helmet_url = %s
                WHERE name = %s AND helmet_url IS NULL
                """,
                [
                    (HELMET_URL_TEMPLATE.format(abbr=abbr), name)
                    for name, abbr in NFL_TEAMS
                ],
            )

            cur.execute("SELECT COUNT(*) FROM teams")
            (count,) = cur.fetchone()
            if count == 0:
                cur.executemany(
                    "INSERT INTO teams (name, helmet_url) VALUES (%s, %s)",
                    [
                        (name, HELMET_URL_TEMPLATE.format(abbr=abbr))
                        for name, abbr in NFL_TEAMS
                    ],
                )
                print(f"[init_db] seeded {len(NFL_TEAMS)} teams", flush=True)
    finally:
        conn.close()


@app.route("/api/teams")
def list_teams():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, helmet_url FROM teams ORDER BY name")
            teams = [{"name": name, "helmet_url": helmet_url} for name, helmet_url in cur.fetchall()]
        return jsonify(teams)
    finally:
        conn.close()


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
