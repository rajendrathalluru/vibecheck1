# VibeCheck Frontend

A lightweight dashboard for the VibeCheck API.

## Features
- Create assessments in both modes:
  - Lightweight from GitHub repo URL
  - Robust from target URL, selected agents, and depth (optional tunnel session)
- View assessment statuses and summary metrics
- Inspect findings in a grid table with search, filter, sort, and pagination
- Click any finding row to view full JSON detail
- Analyze selected finding with AI for summary, root-cause, and actionable fix guidance
- Query Supermemory for similar historical findings from selected finding
- Export current findings view as CSV or JSON
- View security analytics charts:
  - Severity distribution for selected assessment findings
  - Findings trend across recent assessments
- Real-time assessment status updates via WebSocket (no manual refresh needed)
- Optional auto-poll to update running assessments every 5 seconds

## Run
1. Start backend API (from `/Users/rajendrathalluru/Documents/Hackathon/VibeCheck/vibecheck`):
   - `python3 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
2. Serve frontend (from `/Users/rajendrathalluru/Documents/Hackathon/VibeCheck/frontend`):
   - `python3 -m http.server 5173`
3. Open:
   - `http://localhost:5173`
   - API docs page: `http://localhost:5173/docs.html`
   - React dashboard (alternative UI): `http://localhost:5173/react.html`
4. If backend is elsewhere, change the `API Base URL` in the top-right field.
