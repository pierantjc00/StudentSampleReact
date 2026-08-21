# NFL Teams — pipeline test app

A minimal, disposable app for smoke-testing the `se1-deploy-system` pipeline
end to end, matching the layout described in `docs/student-setup-guide.md`:
a `frontend/` (React) and a `backend/` (Flask, Dockerized) folder, nothing
else required.

What it does: on startup the backend creates a `teams` table in its own
Postgres database (via `DATABASE_URL`, injected automatically — nothing here
is hardcoded to a student id, host, or password) and seeds it with the 32
NFL team names if the table is empty. The frontend fetches that list from
the backend and renders it. Loading the page and seeing 32 team names
confirms every layer of the pipeline is working: GitHub push → webhook →
`deploy.sh` → React build → Flask container → shared Postgres → back to the
browser.

## How to use this as your test student

1. Push this repo to a GitHub repo of your own (public or private, doesn't
   matter for this purpose).
2. Onboard it exactly like a real student, using any id you like (e.g.
   `testuser`):

   ```bash
   cd /opt/studentapps
   sudo -u deployer /opt/studentapps/venv/bin/python provision.py add testuser https://github.com/<you>/<this-repo>.git
   ```

3. Open `http://<your-ip-or-domain>/students/testuser/` in a browser — you
   should see the NFL Teams list.
4. Register the printed webhook URL + secret against this same repo in
   GitHub (Settings → Webhooks), push a trivial commit (e.g. edit this
   README), and confirm the page updates automatically after the webhook
   fires — that's the part a one-time manual deploy can't prove.
5. Tear it down when you're done:

   ```bash
   sudo -u deployer /opt/studentapps/venv/bin/python provision.py remove testuser
   ```

## Running it locally (optional, not required to test the pipeline)

```bash
# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql://user:pass@localhost:5432/somedb python app.py

# frontend, in a second terminal
cd frontend
npm install
npm start
```

With no `PUBLIC_URL` set, `npm start` serves from `/`, so you'd also need a
proxy or a temporary edit to `API_URL` in `src/App.js` to reach the backend
on `localhost:5000` — this local-dev path is a convenience, not something
students need for the deploy pipeline itself.
