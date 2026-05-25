# TCG Pricerator 9000

Local web app that watches your Magic: The Gathering collection and tells you which cards are worth selling. Import a [Moxfield](https://www.moxfield.com/) "haves" CSV, set a price threshold, and get a desktop notification when cards cross it.

Prices come from [Scryfall](https://scryfall.com/), which ingests TCGplayer prices daily.

**No accounts. No cloud. All data lives on your computer.**

---

## Install

Requires **Python 3.10+** ([python.org](https://www.python.org/downloads/)).

```bash
pip install git+https://github.com/YOUR_USERNAME/tcg-pricerator
```

Then run it:

```bash
pricerator serve
```

A browser window opens at `http://localhost:5000`.

---

## First-run flow

1. Click **Import CSV** and pick your Moxfield export.  
   *(Moxfield: My Cards → Haves → Export → CSV)*
2. Click **Refresh Prices** — first run downloads ~150 MB from Scryfall, so use Wi-Fi.
3. Open **Settings** to set your sell thresholds (default $1.00 each) and refresh interval.

---

## Features

- Import a Moxfield "haves" CSV (standard, foil, etched, The List `GK1-57` numbers)
- Per-printing thresholds — separate values for nonfoil, foil, and etched
- Automatic background price refresh: 6h / 12h / 24h / Manual
- Desktop notification (Mac + Windows) when cards **newly** cross your threshold  
  *(above→above transitions never re-notify)*
- Card detail screen with 30-snapshot price history chart
- TCGplayer search deep link from each card
- Three themes: **Light**, **Dark**, and **Kawaii** ♡

---

## Run at startup (optional)

### macOS — launchd

Create `~/Library/LaunchAgents/com.pricerator.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>com.pricerator</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/pricerator</string>
    <string>serve</string>
    <string>--no-browser</string>
  </array>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <true/>
  <key>StandardOutPath</key>   <string>/tmp/pricerator.log</string>
  <key>StandardErrorPath</key> <string>/tmp/pricerator.log</string>
</dict>
</plist>
```

> Replace `/usr/local/bin/pricerator` with the output of `which pricerator`.

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.pricerator.plist
```

### Windows — Task Scheduler

1. Open **Task Scheduler** → *Create Basic Task*
2. Trigger: **When I log on**
3. Action: **Start a program**  
   Program: `pricerator` (or full path from `where pricerator`)  
   Arguments: `serve --no-browser`
4. Finish. Pricerator will start silently at login.

---

## Data location

All data (database + settings) is stored in `~/.pricerator/`.  
Override with the `PRICERATOR_DATA` environment variable.

---

## Development

```bash
git clone https://github.com/YOUR_USERNAME/tcg-pricerator
cd tcg-pricerator
pip install -e ".[dev]"
pytest tests/
```

---

## Architecture

```
pricerator/
  config.py       — Settings (JSON on disk, ~/.pricerator/settings.json)
  csv_parser.py   — Moxfield CSV parser
  db.py           — SQLite (card, price_snapshot tables)
  price_math.py   — cents conversion, foil-aware price lookup, threshold-crossing
  scryfall.py     — Scryfall bulk JSON downloader (streaming via ijson)
  refresh.py      — Orchestrates download → snapshot → notify
  notifier.py     — Desktop notifications via plyer
  scheduler.py    — APScheduler background refresh job
  web.py          — Flask routes
  templates/      — Jinja2 + Bootstrap 5 + Chart.js
  __main__.py     — CLI entry point
```

### Why Scryfall instead of TCGplayer directly?

TCGplayer's pricing API requires partner approval and isn't accessible for personal projects. Scryfall is free, well-documented, and ingests TCGplayer prices daily — which is fine for a "is this worth my time to list?" tool. The bulk `default_cards` endpoint lets us update the entire collection in one download (~150 MB) instead of thousands of individual API calls.

---

## Privacy

The only network requests are to `api.scryfall.com` and Scryfall's CDN. No analytics, no crash reporters.
