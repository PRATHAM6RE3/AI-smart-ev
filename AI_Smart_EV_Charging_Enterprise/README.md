# EVSmart Enterprise Demo — AI-Based Smart EV Charging Management

A local, interactive portfolio/company demo built with Flask, SQLite, HTML/CSS/JavaScript, and Chart.js.

## What works

- Responsive multi-view operations dashboard.
- SQLite persistence for vehicles, chargers, bookings, and events.
- Station/charger inventory with connector compatibility.
- Vehicle registration (model, connector, battery capacity, current state of charge).
- Transparent weighted charger recommendation based on estimated energy, duration, configured tariff, priority, and simulated solar share.
- FCFS baseline comparison.
- Booking lifecycle: reserve → start → complete, or cancel.
- SOC update when a session completes.
- Charger status controls and simulated telemetry tick.
- Operational analytics from completed sessions.
- Demand forecast endpoint and chart. Uses a moving-average baseline when there are enough completed sessions; otherwise uses a synthetic illustrative profile.
- JSON endpoints: `/health`, `/api/dashboard`, `/api/stations`, `/api/vehicles`, `/api/recommend`, `/api/bookings`, `/api/analytics`, `/api/forecast`.

## Important honesty note

This is a fully interactive **simulation/demo**, not a production charging network. The scheduling logic is a transparent heuristic, not a trained AI model. Demand forecast falls back to synthetic sample data until there is enough local completed-session history. There is no real charger hardware, OCPP, MQTT, live grid tariff, payment processing, authentication, or external maps integration in this version. The Chart.js library and web font use CDN links, so those visual assets require internet access; core server functionality is local.

## Run on Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/ and enable “Add Python to PATH”.
2. Extract the ZIP file to a normal folder.
3. Open that folder in VS Code.
4. Open **Terminal → New Terminal**.
5. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

This command sequence avoids PowerShell activation policy errors.

6. Open http://127.0.0.1:5000 in your browser.
7. Leave the terminal open while demoing the app.

The local SQLite database `evsmart.db` is created on first startup and stores transactions between restarts.

## Suggested company demo walkthrough (5–7 minutes)

1. Overview: show charger inventory, forecast chart, recent activity, and event feed.
2. Vehicle Fleet: register a test EV or use the seeded vehicles.
3. AI Scheduler: select a vehicle, set target SOC and priority, and compare Smart weighted scoring with FCFS.
4. Reserve a charger; then open Booking Operations and click Start.
5. Complete the session; verify that the vehicle SOC and analytics update.
6. Stations & Chargers: mark an idle charger offline and show that recommendations no longer use it; mark it available again.
7. Run a simulation tick to show the simulated event feed.
8. Explain the current limits and next production steps.

## Architecture

Browser UI → Flask REST endpoints → scheduling / energy calculations → SQLite database → dashboard and analytics.

## Production roadmap

- Train and evaluate a time-series demand model on real anonymized charging data.
- Add role-based authentication and audit trails.
- Add OCPP-compatible charger gateway and MQTT telemetry (hardware + broker required).
- Add real geospatial routing, tariff feeds, payment provider, notifications, and cloud deployment.
- Add automated tests, migrations, observability, rate limiting, and secrets management before production.

## Reset demo data

Use the **Reset demo transactions** button in Booking Operations. It clears bookings and event history while preserving stations, chargers, and vehicles.
