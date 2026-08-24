"""
Starter/test backend for the student deploy pipeline.

On startup, creates a `teams` table (if it doesn't already exist) and seeds
it with the 32 NFL team names + helmet image URLs + last season's win-loss
record the first time it runs against an empty table. Exposes that list
over a small JSON API that the frontend reads.

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

# (name, ESPN team abbreviation, 2025 regular-season wins, losses, ties).
# Helmet images are served from ESPN's public team-logo CDN rather than
# stored in this repo -- the frontend just points an <img> at
# HELMET_URL_TEMPLATE.format(abbr).
NFL_TEAMS = [
    ("Arizona Cardinals", "ari", 3, 14, 0), ("Atlanta Falcons", "atl", 8, 9, 0),
    ("Baltimore Ravens", "bal", 8, 9, 0), ("Buffalo Bills", "buf", 12, 5, 0),
    ("Carolina Panthers", "car", 8, 9, 0), ("Chicago Bears", "chi", 11, 6, 0),
    ("Cincinnati Bengals", "cin", 6, 11, 0), ("Cleveland Browns", "cle", 5, 12, 0),
    ("Dallas Cowboys", "dal", 7, 9, 1), ("Denver Broncos", "den", 14, 3, 0),
    ("Detroit Lions", "det", 9, 8, 0), ("Green Bay Packers", "gb", 9, 7, 1),
    ("Houston Texans", "hou", 12, 5, 0), ("Indianapolis Colts", "ind", 8, 9, 0),
    ("Jacksonville Jaguars", "jax", 13, 4, 0), ("Kansas City Chiefs", "kc", 6, 11, 0),
    ("Las Vegas Raiders", "lv", 3, 14, 0), ("Los Angeles Chargers", "lac", 11, 6, 0),
    ("Los Angeles Rams", "lar", 12, 5, 0), ("Miami Dolphins", "mia", 7, 10, 0),
    ("Minnesota Vikings", "min", 9, 8, 0), ("New England Patriots", "ne", 14, 3, 0),
    ("New Orleans Saints", "no", 6, 11, 0), ("New York Giants", "nyg", 4, 13, 0),
    ("New York Jets", "nyj", 3, 14, 0), ("Philadelphia Eagles", "phi", 11, 6, 0),
    ("Pittsburgh Steelers", "pit", 10, 7, 0), ("San Francisco 49ers", "sf", 12, 5, 0),
    ("Seattle Seahawks", "sea", 14, 3, 0), ("Tampa Bay Buccaneers", "tb", 8, 9, 0),
    ("Tennessee Titans", "ten", 3, 14, 0), ("Washington Commanders", "wsh", 5, 12, 0),
]

HELMET_URL_TEMPLATE = "https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db(retries: int = 10, delay_seconds: int = 2) -> None:
    """Creates + seeds the teams table, and migrates older databases that
    already have a `teams` table without the helmet_url / wins / losses /
    ties columns.

    CREATE TABLE IF NOT EXISTS only helps brand-new databases -- an
    existing `teams` table (e.g. from before these columns existed) is
    left untouched by it, and the seed step below only ever runs once
    (when the table is empty), so it would never backfill existing rows
    either. That's why this explicitly ALTERs the table and backfills any
    row missing the new columns, every time this runs; all of these
    statements are no-ops on a database that's already up to date, so this
    stays safe to call on every container start/redeploy.

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
                    helmet_url TEXT,
                    wins INTEGER,
                    losses INTEGER,
                    ties INTEGER
                )
                """
            )

            # Migration for tables created before these columns existed.
            cur.execute(
                """
                ALTER TABLE teams
                    ADD COLUMN IF NOT EXISTS helmet_url TEXT,
                    ADD COLUMN IF NOT EXISTS wins INTEGER,
                    ADD COLUMN IF NOT EXISTS losses INTEGER,
                    ADD COLUMN IF NOT EXISTS ties INTEGER
                """
            )

            # Backfill any row (old or newly created above) that's missing
            # its helmet_url and/or record -- e.g. the 32 rows seeded by a
            # pre-migration deploy. helmet_url and wins are backfilled
            # independently (separate IS NULL checks) so a database that
            # already has one but not the other still gets the missing
            # piece filled in.
            cur.executemany(
                """
                UPDATE teams SET helmet_url = %s
                WHERE name = %s AND helmet_url IS NULL
                """,
                [
                    (HELMET_URL_TEMPLATE.format(abbr=abbr), name)
                    for name, abbr, wins, losses, ties in NFL_TEAMS
                ],
            )
            cur.executemany(
                """
                UPDATE teams SET wins = %s, losses = %s, ties = %s
                WHERE name = %s AND wins IS NULL
                """,
                [
                    (wins, losses, ties, name)
                    for name, abbr, wins, losses, ties in NFL_TEAMS
                ],
            )

            cur.execute("SELECT COUNT(*) FROM teams")
            (count,) = cur.fetchone()
            if count == 0:
                cur.executemany(
                    """
                    INSERT INTO teams (name, helmet_url, wins, losses, ties)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        (name, HELMET_URL_TEMPLATE.format(abbr=abbr), wins, losses, ties)
                        for name, abbr, wins, losses, ties in NFL_TEAMS
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
            cur.execute(
                "SELECT name, helmet_url, wins, losses, ties FROM teams ORDER BY name"
            )
            teams = [
                {
                    "name": name,
                    "helmet_url": helmet_url,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                }
                for name, helmet_url, wins, losses, ties in cur.fetchall()
            ]
        return jsonify(teams)
    finally:
        conn.close()


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
