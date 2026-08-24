import React, { useEffect, useState } from "react";

// process.env.PUBLIC_URL is set at build time by deploy.sh
// (PUBLIC_URL=/students/<student_id> npm run build), so this resolves to
// /students/<id>/api/teams in production and just /api/teams when running
// locally with `npm start` (where PUBLIC_URL is empty).
const API_URL = `${process.env.PUBLIC_URL}/api/teams`;

function App() {
  const [teams, setTeams] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(API_URL)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Request to ${API_URL} failed: HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        setTeams(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div
      style={{
        fontFamily: "system-ui, sans-serif",
        maxWidth: 480,
        margin: "3rem auto",
        padding: "0 1rem",
        lineHeight: 1.5,
      }}
    >
      <h1>NFL Teams</h1>
      <p style={{ color: "#666" }}>
        This list is loaded from Postgres through the backend at{" "}
        <code>{API_URL}</code> — if you're seeing 32 team names below, the
        full pipeline is working end to end: GitHub push → webhook →
        deploy.sh → React build → Flask → shared Postgres.
      </p>

      {loading && <p>Loading…</p>}
      {error && (
        <p style={{ color: "crimson" }}>
          Couldn't load teams: {error}
        </p>
      )}
      {!loading && !error && (
        <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {teams.map((team) => (
            <li
              key={team.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.35rem 0",
              }}
            >
              <img
                src={team.helmet_url}
                alt={`${team.name} helmet`}
                width={36}
                height={36}
                style={{ objectFit: "contain", flexShrink: 0 }}
              />
              <span>{team.name}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default App;
