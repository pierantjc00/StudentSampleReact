"""
Starter/test backend for the student deploy pipeline.

On startup, creates a `teams` table (if it doesn't already exist) and seeds
it with the 32 NFL team names the first time it runs against an empty
table. Exposes that list over a small JSON API that the frontend reads.

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

NFL_TEAMS = [
    "Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills",
    "Carolina Panthers", "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns",
    "Dallas Cowboys", "Denver Broncos", "Detroit Lions", "Green Bay Packers",
    "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Kansas City Chiefs",
    "Las Vegas Raiders", "Los Angeles Chargers", "Los Angeles Rams", "Miami Dolphins",
    "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants",
    "New York Jets", "Philadelphia Eagles", "Pittsburgh Steelers", "San Francisco 49ers",
    "Seattle Seahawks", "Tampa Bay Buccaneers", "Tennessee Titans", "Washington Commanders",
]


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db(retries: int = 10, delay_seconds: int = 2) -> None:
    """Creates + seeds the teams table. Idempotent -- safe to call on every
    container start/redeploy, since CREATE TABLE IF NOT EXISTS plus the
    row-count check mean it only seeds once, ever, per database.

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
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            cur.execute("SELECT COUNT(*) FROM teams")
            (count,) = cur.fetchone()
            if count == 0:
                cur.executemany(
                    "INSERT INTO teams (name) VALUES (%s)",
                    [(name,) for name in NFL_TEAMS],
                )
                print(f"[init_db] seeded {len(NFL_TEAMS)} teams", flush=True)
    finally:
        conn.close()


@app.route("/api/teams")
def list_teams():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM teams ORDER BY name")
            teams = [row[0] for row in cur.fetchall()]
        return jsonify(teams)
    finally:
        conn.close()


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
