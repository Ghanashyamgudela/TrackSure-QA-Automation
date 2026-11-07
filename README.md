# TrackSure

TrackSure is a FastAPI courier tracking app with a server-rendered operations dashboard, SQLite persistence, and Selenium/API/database tests.

## Run locally

Activate the virtual environment and configure an application signing key and initial administrator before starting the server. Keep these values private; do not commit them.

```powershell
.\venv\Scripts\Activate.ps1
$env:TRACKSURE_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:TRACKSURE_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:TRACKSURE_BOOTSTRAP_ADMIN_PASSWORD = "replace-with-a-private-password-at-least-12-characters"
python -m uvicorn applications.main:app --reload
```

The administrator account is created the first time the app starts with both bootstrap variables configured. Existing administrator passwords are not overwritten on later starts. Sign in at `/login`; administrators can add or deactivate staff from the dashboard. Operators can update shipment status and delay reasons. Only administrators can manage staff accounts.

The session is a signed, HTTP-only cookie and expires after 12 hours. State-changing staff requests also require a CSRF token. Use HTTPS in production; the session cookies are marked secure automatically for HTTPS requests.

To run API and database tests, start the app with the same environment variables in one terminal, then run in another terminal with those credentials set:

```powershell
$env:TRACKSURE_DATABASE_URL = "sqlite:///./tracksure_test.db"
python -m pytest tests\api\ tests\database\
```

Set that database URL in both terminals (including before starting Uvicorn) so test shipments stay out of `tracksure.db`. The GitHub Actions workflow uses its own isolated database and test-only credentials. Never reuse CI credentials outside CI.

## Features

- Dashboard analytics refresh every 30 seconds; delivery success is delivered shipments divided by all shipments.
- Seven-day shipment volume and current status distribution.
- Tracking timeline with UTC event times, a five-calendar-day estimated delivery date, and delivery confirmation details.
- Shipments are flagged as delayed when they have had no status movement for 24 hours. Staff can record a reason.
- Delivery confirmation (receiver name and remarks; optional typed signature) is required before marking a shipment delivered. The public tracking view does not expose the typed signature.
- Status changes and cancellations are recorded in an audit log with the actor and timestamp.
- Shipment search, status filter, sort, and CSV export.

The first startup creates new feature tables in the configured SQLite database. Existing shipment and tracking-history records are retained.
