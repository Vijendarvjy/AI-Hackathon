# AI Hackathon Website (School Students)

A simple, working website for a school AI Hackathon under the theme **"Meri Samasya, Mera Samadhan" (My Problem, My Solution)**.

Students solve a real problem from their own home, school, or village. Judges reward thinking about the problem over technical polish.

## Features

- **Public pages**
  - Home page with theme, tracks/example problems, and judging parameters
  - Student registration (solo or group) with a unique auto-generated **registration number**
- **Admin login**
  - Dashboard with registration stats
  - View all registrations (team details, members, problem/solution)
  - View evaluation results (average total and per-parameter scores across judges)
  - Manage/create judge accounts
- **Judge panel login**
  - View assigned/available registrations and evaluation status
  - Evaluate each registration on **five parameters** (1–10 each) with optional comments
  - Submit or update evaluations

## Tracks included

- Safe and healthy communities
- Farming and local livelihoods
- Climate and environment
- Better learning at school
- Inclusion and girls’ safety
- AI for good (optional, Class 8-9)

## Judging parameters (5)

Each parameter is scored from **1 to 10** (max total 50 per judge):

1. **Problem Understanding** – clarity and depth of understanding of the real-life problem (Meri Samasya)
2. **Solution Relevance & Impact** – how well the solution addresses the problem and benefits the community (Mera Samadhan)
3. **Creativity & Innovation** – originality and thoughtful approach
4. **Feasibility & Implementation** – practicality and realistic implementation/demonstration
5. **Presentation & Explanation** – clarity of communication and ability to discuss limitations or improvements

## Registration rules (as implemented)

- **Type:** Solo or Group
- **Group size:** **any number** of members (group registrations must include at least one additional member besides the leader; there is no upper limit)
- **Registration number:** auto-generated unique number on successful submission (format: `AIH-<year>-<sequence>`, e.g. `AIH-2026-0001`)
- Captures track, project/solution title and description, school, leader/student details, and optional group member details/contact info

## Tech stack

- Python 3 + Flask
- SQLite database (`instance/hackathon.db`, auto-created on first run)
- HTML/CSS (Jinja templates)

## Setup and run (Windows / PowerShell)

1. **Install dependencies** (from the project folder):

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. **Run the app**:

   ```powershell
   python app.py
   ```

3. Open in your browser: **http://localhost:5000**

The database and default accounts are created automatically on first run.

## Default demo accounts

> **Change these credentials before using in a real event.**

- **Admin**
  - Username: `admin`
  - Password: `admin123`
- **Judge (demo)**
  - Username: `judge`
  - Password: `judge123`

Admins can create additional judge accounts from **Admin Dashboard → Manage Judges**.

## Project structure

- `app.py` – Flask application, routes, database initialization, and configuration
- `requirements.txt` – Python dependencies
- `templates/` – HTML templates (home, registration, admin, judge, evaluation)
- `static/style.css` – styles
- `instance/hackathon.db` – SQLite database (created at runtime)

## Notes / customization

- Judging parameters and theme/track text are defined as constants near the top of `app.py` for easy customization. Group size is unlimited (solo or group with any number of members).
- Set a secure `SECRET_KEY` environment variable for production-like use.
- For a real deployment, use a production WSGI server and secure credential management.

## Netlify deployment (full Flask app)

This repo includes a Netlify Functions setup for deploying the full Flask app:

- [netlify.toml](netlify.toml) - build/publish/functions config and redirect to the Flask function
- [netlify/functions/app.py](netlify/functions/app.py) - serverless-wsgi handler wrapping the Flask app
- [netlify/functions/requirements.txt](netlify/functions/requirements.txt) - Python dependencies for the function runtime
- [netlify/public/.gitkeep](netlify/public/.gitkeep) - keeps the publish directory in git (publish dir is required by Netlify)

### Deploy steps

1. Push the repository to GitHub.
2. In Netlify, create a new site from the repo.
3. Use the repo defaults from `netlify.toml`:
   - Build command: `npm run build`
   - Publish directory: `netlify/public`
   - Functions directory: `netlify/functions`
4. Set environment variables as needed (at minimum, set a strong `SECRET_KEY`).

### Important limitation

The app uses SQLite. On Netlify Functions, the database is stored in `/tmp` and is **ephemeral** - data is reset on cold starts/redeploys and is not shared across function instances. For production use, migrate to a persistent managed database (for example PostgreSQL) and update the app's database configuration.

### Static-only alternative

For a static landing page only (no backend features), deploy the [netlify-static/](netlify-static/) folder. See [netlify-static/netlify.toml](netlify-static/netlify.toml).
