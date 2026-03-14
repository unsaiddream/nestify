<img src="ui/logo.png" width="80" alt="Nestify logo" />

# Nestify — AI Real Estate Agent for Realtors

Nestify is a local desktop web app that automates a real estate agent's workflow on **Krisha.kz** — Kazakhstan's largest property platform. It runs entirely on your computer, operates through your own Krisha.kz account, and uses Google Gemini as its AI brain.

---

## Who is it for?

**Real estate agents in Kazakhstan** who:
- Manually browse Krisha.kz every day looking for listings that match what their clients need
- Spend hours sending the same introductory messages to sellers one by one
- Manage multiple buyers or renters simultaneously

Nestify turns all of that into a background process.

---

## How it works

```
Add client (budget, area, district, rooms)
        ↓
Agent opens Krisha.kz using your logged-in account
        ↓
Finds new listings matching the filters
        ↓
Gemini scores each listing 1–10 against client criteria
        ↓
Approved listings (score ≥ 6) → agent sends a personalized message to the seller
        ↓
Dashboard shows everything: listings, scores, sent messages, activity log
```

---

## Features

- **Multi-client** — run searches for multiple buyers/renters at the same time
- **Map polygon search** — draw a custom area on the interactive map to restrict the search zone precisely
- **AI scoring** — Gemini evaluates price, area, rooms, location, and description quality
- **Auto-messaging** — generates a natural, personalized message for each approved listing
- **Custom message templates** — define your own template per client; Gemini adapts it
- **Human-like behavior** — deliberate delays between actions to avoid detection
- **Local-first** — all data stays on your machine; nothing is sent to any cloud
- **Dark + Light theme** — dark mode by default; switch to iOS-style frosted glass light mode

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI (async) |
| Browser automation | Playwright (Chromium, persistent profile) |
| AI | Google Gemini API |
| Database | SQLite (local) |
| Frontend | Vanilla HTML/CSS/JS — no framework |

---

## Installation

```bash
git clone https://github.com/unsaiddream/nestify.git
cd nestify
pip install -r requirements.txt
playwright install chromium
python main.py
```

This starts the server on `localhost:8000` and opens the browser automatically.

---

## Requirements

- Python 3.11+
- A **Google Gemini API key** → [Get one free at Google AI Studio](https://aistudio.google.com/app/apikey)
- A **Krisha.kz account** (the agent acts on your behalf — same as any CRM)

---

## Setup (first run)

1. Open [localhost:8000](http://localhost:8000)
2. Enter your Gemini API token → saved locally in SQLite, never uploaded
3. Go to **Settings → Open Browser** → log in to Krisha.kz manually (one time only, session is saved)
4. Go to **Clients** → add a client with search criteria
5. Optionally go to **Map** → draw a polygon search zone for that client
6. Hit **Start Agent** — it runs in the background

---

## Project structure

```
nestify/
├── main.py                  # Entry point — starts FastAPI and opens browser
├── api/
│   ├── server.py            # FastAPI app, static file serving
│   └── routes/
│       ├── auth.py          # Gemini token management
│       ├── agent.py         # Start/stop agent, status
│       └── listings.py      # Clients, listings, messages CRUD
├── agent/
│   ├── browser.py           # Playwright — search, parse listings, send messages
│   ├── gemini.py            # Gemini API — analyze listings, generate messages
│   └── analyzer.py          # Agent loop — orchestrates search + analysis + messaging
├── database/
│   └── db.py                # SQLite — settings, clients, listings, messages, action log
├── ui/
│   ├── index.html           # Single-page app
│   ├── styles.css           # Dark theme + iOS glass light theme
│   └── app.js               # Frontend logic
├── logo.png                 # App logo (place in ui/logo.png to show in browser)
└── requirements.txt
```

---

## Important notes

- The agent acts **through the realtor's own account** — this is standard CRM behavior, not scraping
- Krisha.kz session is preserved via Playwright's persistent browser profile (`browser_profile/`)
- Messages are personalized by Gemini for each specific listing
- The agent never sends bulk spam — it processes listings one by one with human-like pacing

---

## License

MIT
