# World Cup 2026 Dashboard

A personal Streamlit dashboard and Intralox World Cup Hub for tracking the FIFA World Cup 2026. It is built for private World Cup planning and viewing only. It is not a betting app, sportsbook tool, or public gambling product.

The app is still local-first, but the project is prepared for later deployment on Streamlit Community Cloud with `app.py` as the entrypoint.

## What It Does

- Tracks World Cup teams, groups, fixtures, brackets, rankings, odds snapshots, and an Intralox competition board.
- Creates a local SQLite database automatically for local development.
- Supports optional API integrations when keys are present.
- Supports an optional app password for personal sharing.
- Supports `SHARED_CORE_READ_ONLY_MODE` for hosted sharing that protects official World Cup data while allowing personal preferences.

## Run Locally

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If dependencies are already installed:

```powershell
streamlit run app.py
```

Local data is stored in:

```text
data/worldcup.db
```

The app creates `data/` and `data/imports/` if they are missing.

## Local Secrets

Copy the example file:

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Then edit `.streamlit/secrets.toml` locally:

```toml
THE_ODDS_API_KEY = "your-real-the-odds-api-key"
BALLDONTLIE_API_KEY = "your-real-balldontlie-api-key"
FOOTBALL_DATA_API_KEY = "your-real-football-data-api-key"

APP_PASSWORD = ""
SHARED_CORE_READ_ONLY_MODE = false
```

Never commit `.streamlit/secrets.toml`. API keys are read from Streamlit secrets, not hardcoded in code.

## Optional Password

Set this in `.streamlit/secrets.toml` or Streamlit Cloud secrets:

```toml
APP_PASSWORD = "choose-a-private-password"
```

If `APP_PASSWORD` is missing or blank, the app opens normally. If it is set, users must enter the password before the dashboard is shown. A logout button appears in the sidebar.

## Shared Core Read-Only Mode

For a hosted app that others can view safely, set:

```toml
SHARED_CORE_READ_ONLY_MODE = true
```

The older `SHARED_READ_ONLY_MODE` name is still supported for backward compatibility, but new deployments should use `SHARED_CORE_READ_ONLY_MODE`.

In shared core read-only mode:

- View pages remain available for rankings, odds, groups, fixtures, charts, brackets, and simulations.
- Official/core data changes are hidden or disabled, including CSV imports, API refreshes, admin edits, teams, groups, fixtures, rankings, odds snapshots, and official results.
- Users can still save personal preferences: favorite teams, watchlists, bracket picks, predictions, notes, dark horses, overrated teams, and underrated teams.
- No user account is required. No GitHub account, Streamlit account, Google account, display name, or PIN is required.
- Personal preferences are saved in the user's browser/device with browser storage.
- If browser storage is unavailable, preferences fall back to the current Streamlit session and are labeled as session-only.

Preferences are tied to the browser/device. They may not transfer if the user switches browsers, switches devices, uses private/incognito mode, clears site data, or the app URL changes. Browser preferences are not appropriate for sensitive information.

A shared password only controls access to the app; it does not identify individual users by itself. User favorites and picks should be stored through browser preference storage, not in `st.secrets`. For true cross-device persistence in a hosted app, user preferences should eventually move to a hosted database such as Supabase, Neon Postgres, Firebase, or similar.

## Deploy To Streamlit Community Cloud

1. Push this project to a private or public GitHub repository.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Create a new app from the GitHub repo.
4. Set the main file path to:

```text
app.py
```

5. In the Streamlit app settings, open **Secrets** and paste your secrets in TOML format.
6. For personal sharing, set `APP_PASSWORD`.
7. For hosted sharing, set `SHARED_CORE_READ_ONLY_MODE = true`.
8. Deploy the app and share the generated Streamlit URL with the people who should have access.

Example cloud secrets:

```toml
THE_ODDS_API_KEY = "your-real-the-odds-api-key"
BALLDONTLIE_API_KEY = "your-real-balldontlie-api-key"
FOOTBALL_DATA_API_KEY = "your-real-football-data-api-key"
APP_PASSWORD = "choose-a-private-password"
SHARED_CORE_READ_ONLY_MODE = true

[odds]
sport_key = ""
regions = "us"
bookmakers = ""
```

## API Keys

All API keys are optional. Missing keys should show friendly warnings instead of crashing the app.

- `THE_ODDS_API_KEY`: optional odds snapshots from The Odds API.
- `BALLDONTLIE_API_KEY`: reserved for optional future sports-data integrations.
- `FOOTBALL_DATA_API_KEY`: optional football-data.org fixture, team, and standings calls.

The app still supports older local key names such as `FOOTBALL_DATA_TOKEN` and `[api_keys].odds_provider`, but new deployments should use the top-level names above.

## Data Imports

Starter import templates live in:

```text
data/imports/teams.csv
data/imports/groups.csv
data/imports/fixtures.csv
data/imports/fifa_rankings.csv
data/imports/odds.csv
```

Local/admin mode supports CSV or JSON imports for:

- `teams`
- `groups`
- `fixtures`
- `fifa_rankings`
- `odds`

In shared core read-only mode, upload/import controls are disabled.

## Project Structure

```text
world_cup_2026_dashboard/
    app.py
    requirements.txt
    README.md
    .streamlit/
        secrets.toml.example
    data/
        imports/
    src/
        config.py
        database.py
        data_loader.py
        storage/
            browser_preferences.py
            browser_preferences_component/
            storage.py
        api_clients/
        pages/
        analytics/
        utils/
```

## Safety Notes

- Do not commit `.streamlit/secrets.toml`.
- Do not commit local SQLite databases unless intentionally bundling read-only seed data.
- Odds are informational only.
- This app is for personal World Cup tracking and sharing, not wagering or real-money transactions.
