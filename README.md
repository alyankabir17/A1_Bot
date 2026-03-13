# Goethe A1 Booking Helper Bot

A Selenium-based automation tool that monitors the [Goethe-Institut Pakistan](https://www.goethe.de/ins/pk/en/spr/prf/gzsd1.cfm) exam booking page for available **Goethe-Zertifikat A1** slots and automates the initial booking navigation steps. The bot performs a **3-step automated flow** (Book Now → Continue → Book for Myself) and then **completely stops**, handing control to the user for manual login and form submission.

---

## Table of Contents

- [Disclaimer](#disclaimer)
- [Features](#features)
- [3-Step Automation Flow](#3-step-automation-flow)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [CSV Format (Recommended)](#csv-format-recommended)
  - [Configuration Fields](#configuration-fields)
  - [Exam Schedule (Multi-City)](#exam-schedule-multi-city)
- [Usage](#usage)
  - [Basic Run](#basic-run)
  - [Scheduled Monitoring](#scheduled-monitoring)
  - [Burst Mode](#burst-mode)
  - [Headless Mode](#headless-mode)
  - [All CLI Options](#all-cli-options)
- [Architecture & Key Components](#architecture--key-components)
- [Safety & Anti-Detection Measures](#safety--anti-detection-measures)
- [Selector Reference](#selector-reference)
- [Logging](#logging)
- [CI/CD](#cicd)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Disclaimer

> **This tool is intended ONLY for personal, fair, and lawful use by a single user.**
>
> - You are responsible for complying with Goethe-Institut's Terms of Service, local laws, and any anti-abuse rules.
> - Automation of booking systems may lead to account or IP bans.
> - The script intentionally **stops after the 3-step navigation** — it does NOT auto-submit registration forms or log in on your behalf.
> - Use conservative polling intervals and human-like delays at all times.

---

## Features

| Feature | Description |
|---|---|
| **Slot Monitoring** | Continuously polls the Goethe exam finder page for bookable slots |
| **3-Step Auto-Navigation** | Automates Book Now → Continue → Book for Myself, then stops |
| **Date-Based City Selection** | Automatically targets the correct exam center based on your exam schedule (e.g. Lahore on Mar 13, Karachi on Mar 27) |
| **Burst Mode** | Fast-polls around the exact booking-open time for maximum responsiveness |
| **Human-Like Behavior** | Randomised delays (1.5 – 5.5s), mouse jitter, and natural click patterns |
| **Anti-Block Detection** | Detects 429/503/Cloudflare challenges and backs off with cooling periods |
| **Desktop Notifications** | Sends OS-level alerts via `plyer` when a slot is found or errors occur |
| **Single-Tab Enforcement** | Prevents the browser from opening multiple tabs |
| **No Registration Automation** | Stops after booking flow; login and form submission stay manual |
| **Structured Logging** | Logs every action to both console and a daily log file |
| **Simple Config** | Uses CSV configuration only |

> Note: The bot is now **CSV-only**. `config.json` is no longer supported.

---

## 3-Step Automation Flow

The bot automates exactly three navigation steps, then **completely halts** so you can manually log in and fill out the form:

### Step 1 — Refresh & Click "Book Now"
- Opens the Goethe A1 booking page
- Begins refresh logic **5–10 seconds before** the scheduled booking time
- If the **Book** button is not visible:
  - **Before scheduled time** → refreshes every 5 seconds
  - **After scheduled time** → refreshes every 2–3 seconds (burst mode)
- Once the **Book** button appears, clicks it

### Step 2 — Click "Continue"
- After clicking **Book**, the website loads the **Selection page** showing exam details
- Waits for the page to load using explicit waits (server may be slow during booking time)
- Locates and clicks the **Continue** button

### Step 3 — Click "Book for Myself" & STOP
- After clicking **Continue**, the **Participant page** appears
- Locates and clicks the **Book for myself** button
- This redirects to the **Goethe login page**

### Critical Stop Point
At this point the bot:
- **Completely stops execution**
- **Disables any autofill**
- **Disables login automation**
- The user **manually logs in and fills the form**

---

## How It Works

```
┌────────────────────┐
│  Load config (CSV  │
│  or JSON)          │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Wait until        │
│  --start-monitoring│
│  -at time          │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Launch Chrome via │
│  Selenium          │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐     No slots
│  Step 1: Open page │◄──────────────┐
│  & refresh/poll    │               │
└────────┬───────────┘               │
         │                           │
         ▼                           │
┌────────────────────┐               │
│  Resolve target    │               │
│  city from schedule│               │
└────────┬───────────┘               │
         │                           │
         ▼                           │
┌────────────────────┐     No        │
│  Detect "Book Now" ├──────────────►│
│  button?           │   (sleep/poll)│
└────────┬───────────┘               │
         │ Yes                       │
         ▼                           │
┌────────────────────┐               │
│  Click "Book Now"  │               │
│  for matched city  │               │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Step 2: Click     │
│  "Continue"        │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Step 3: Click     │
│  "Book for myself" │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  STOP — User       │
│  logs in & fills   │
│  form manually     │
└────────────────────┘
```

---

## Prerequisites

- **Python 3.9+**
- **Google Chrome** (installed on your system)
- **ChromeDriver** — managed automatically by `webdriver-manager`
- **Linux / macOS** (Windows works too, but `setup.sh` is bash-only)

---

## Installation

### Quick Setup (Linux / macOS)

```bash
git clone https://github.com/alyankabir17/A1_Bot.git
cd A1_Bot
chmod +x setup.sh
./setup.sh
```

This will:
1. Create a Python virtual environment in `.venv/`
2. Install all dependencies from `requirements.txt`

### Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| `selenium` | >= 4.10 | Browser automation |
| `webdriver-manager` | >= 4.0.0 | Auto-downloads matching ChromeDriver |
| `plyer` | >= 2.1.0 | Cross-platform desktop notifications |

---

## Configuration

The bot reads runtime options from `config.csv`.

### CSV Format (Recommended)

Create a `config.csv` file:

```csv
full_name,passport_number,date_of_birth,gender,nationality,email,phone,preferred_language,exam_schedule
John Doe,AB1234567,15/08/2000,Male,Pakistan,john@example.com,+923001234567,English,2026-03-13T10:26:00:Lahore;2026-03-27:Karachi
```

### Configuration Fields

| Field | Required | Description | Aliases |
|---|---|---|---|
| `full_name` | No | Optional profile data (unused in booking flow) | — |
| `email` | No | Optional profile data (unused in booking flow) | — |
| `passport_number` | No | Passport / ID number | — |
| `date_of_birth` | No | Date of birth (DD/MM/YYYY) | — |
| `gender` | No | Male / Female / Other | — |
| `nationality` | No | Your nationality | — |
| `phone` | No | Optional profile data (unused in booking flow) | `mobile` |
| `city_preferred` | No | Static fallback city (used only if `exam_schedule` is not set) | `preferred_center` |
| `preferred_language` | No | Exam language (e.g. English) | `exam_language` |
| `exam_schedule` | No | Date-to-city mapping for automatic city selection (see below) | — |

### Exam Schedule (Multi-City with Hardcoded Times)

When multiple exam dates are held in different cities, use `exam_schedule` to let the bot **automatically target the correct city** based on the current date. You can also **hardcode the exact booking-open time** for each exam — the bot will automatically activate **burst mode** at that time without needing `--exam-time`.

**How it works:**
- The bot checks today's date against the schedule on every poll cycle
- It picks the **nearest upcoming** (or today's) exam date and targets that city
- If a `time` is set for that exam, burst mode activates automatically at that exact time
- Once that exam date passes, it automatically switches to the next city
- If all dates have passed, the last city is used as a fallback

**Example:** Lahore on Mar 13 at 10:26, Karachi on Mar 27:

| Today's Date | Bot Targets | Burst Mode |
|---|---|---|
| Feb 21 – Mar 13 | **Lahore** (nearest upcoming) | Activates at **10:26:00** on Mar 13 |
| Mar 14 – Mar 27 | **Karachi** (Lahore date passed) | No burst (no time set) |
| After Mar 27 | **Karachi** (last fallback) | — |

**CSV format** (semicolon-separated `DATETIME:CITY` pairs):
```
2026-03-13T10:26:00:Lahore;2026-03-27:Karachi
```

> **Priority:** Hardcoded `time` in `exam_schedule` takes precedence over the `--exam-time` CLI flag. If the schedule has a time for the upcoming exam, `--exam-time` is ignored.
>
> `exam_schedule` also takes precedence over `city_preferred`. If `exam_schedule` is set, `city_preferred` is ignored.

---

## Usage

### Basic Run

```bash
source .venv/bin/activate
python booking_helper.py --config config.csv --start-monitoring-at now
```

### Scheduled Monitoring

Start monitoring at a specific date/time (local timezone):

```bash
python booking_helper.py \
  --config config.csv \
  --start-monitoring-at 2026-02-20T23:00:00
```

The script will sleep until the specified time, then begin polling.

### Burst Mode

When you know exactly when slots open, burst mode fast-polls around that time.

**Automatic (recommended):** Hardcode the time in `exam_schedule` (see above). The bot will auto-activate burst mode:

```bash
# Just run — burst at 10:26 on Mar 13 is already in config
python booking_helper.py --config config.csv --start-monitoring-at now
```

**Manual override:** Use `--exam-time` if you don't want to use the schedule:

```bash
python booking_helper.py \
  --config config.csv \
  --start-monitoring-at now \
  --exam-time 10:26:00
```

Burst mode activates **5 seconds before** and stays active **50 seconds after** the specified time, polling every **3–5 seconds** (vs the normal 45s interval). During burst:
- The page is refreshed instead of fully reloaded (faster)
- Block detection is skipped (can't afford the cooldown)
- Site crash retries happen every 1.5 seconds

### Headless Mode

Run without a visible browser window (not recommended — you can't manually review):

```bash
python booking_helper.py \
  --config config.csv \
  --start-monitoring-at now \
  --use-headless true
```

### All CLI Options

| Option | Default | Description |
|---|---|---|
| `--config` | `config.csv` | Path to `config.csv` |
| `--start-monitoring-at` | `now` | ISO datetime (local) or `now` |
| `--poll-interval-seconds` | `45` | Seconds between each poll cycle |
| `--use-headless` | `false` | Run Chrome in headless mode |
| `--exam-time` | `now` | `'now'`, `HH:MM:SS`, or ISO datetime for burst anchor time |

---

## Architecture & Key Components

```
A1_Bot/
├── booking_helper.py                # Main script (all logic)
├── config.csv                       # User data (CSV format)
├── goethe_a1_booking_bot_update.md  # Update notes / spec
├── requirements.txt                 # Python dependencies
├── setup.sh                         # One-command environment setup
├── jenkinsfile                      # CI/CD pipeline definition
└── README.md                        # This file
```

### Core Functions

| Function | Purpose |
|---|---|
| `load_user_data()` | Parses CSV config |
| `create_driver()` | Launches Chrome with anti-detection flags |
| `monitor_and_book()` | Main polling loop with burst mode support |
| `wait_for_finder()` | Waits for the exam finder widget to load |
| `find_book_buttons()` | Locates clickable "Book" / "Next" buttons via XPath + CSS fallback |
| `pick_preferred_button()` | Selects the button matching the dynamically resolved city |
| `parse_exam_schedule()` | Parses date/time/city schedule from config string |
| `get_scheduled_city()` | Returns the target city for the nearest upcoming exam date |
| `get_scheduled_exam_dt()` | Returns burst-mode datetime from schedule (auto-burst) |
| `human_move_and_click()` | Scrolls, moves mouse with jitter, and clicks |
| `is_blocked_response()` | Detects Cloudflare / rate-limit pages |
| `is_burst_window()` | Checks if current time is within burst window |
| `notify()` | Sends desktop notification via plyer |

---

## Safety & Anti-Detection Measures

The script is designed to be **polite and undetectable**:

1. **Single Session** — One browser, one tab, no parallel sessions
2. **One Slot Per Run** — Stops after completing the 3-step navigation
3. **Human-Like Delays** — Random pauses (1.5–5.5s) between every interaction
4. **Mouse Jitter** — Small random offsets on mouse movements
5. **Backoff on Errors** — Exponential backoff (3s base, 60s cap) on failures
6. **Rate-Limit Detection** — Detects 429/503 responses and cools down for 2–5 minutes
7. **Cloudflare Detection** — Identifies "checking your browser" and similar pages
8. **Anti-Automation Flags** — `--disable-blink-features=AutomationControlled`
9. **No Auto-Submit** — Stops at the login page; never submits forms or logs in
10. **Graceful Shutdown** — Handles `Ctrl+C` cleanly, closes browser on exit

---

## Selector Reference

If the Goethe website changes its HTML structure, update these constants in `booking_helper.py`:

| Constant | Current Value | Purpose |
|---|---|---|
| `finder_container` | `#pr_finder_9523459`, `.pr-finder` | Exam finder widget container |
| `book_button_xpath` | XPath matching "Book"/"Next"/"Book now" with class `standard` | Primary button selector |
| `book_button_fallback_css` | `a.standard, button.standard` | Fallback button selector |

---

## Logging

The script creates a daily log file named `booking_helper_YYYY-MM-DD.log` in the working directory. All actions, warnings, and errors are logged to both the file and stdout.

Example log output:

```
2026-03-13 10:25:55,234 [INFO] Opening monitor page: https://www.goethe.de/ins/pk/en/spr/prf/gzsd1.cfm
2026-03-13 10:26:01,891 [INFO] BURST: Found 2 clickable button(s).
2026-03-13 10:26:02,123 [INFO] Step 1: Clicking "Book Now" button.
2026-03-13 10:26:05,456 [INFO] Step 2: Clicking "Continue" button.
2026-03-13 10:26:08,789 [INFO] Step 3: Clicking "Book for myself" button.
2026-03-13 10:26:10,012 [INFO] Navigation complete. Bot stopped. Please log in and fill the form manually.
```

---

## CI/CD

A `jenkinsfile` is included for Jenkins pipeline integration. Configure it to run linting, dependency checks, or deployment tasks as needed.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **ChromeDriver version mismatch** | `webdriver-manager` handles this automatically. Update with `pip install -U webdriver-manager` |
| **"Exam finder container did not load"** | The page structure may have changed. Update `SELECTOR_REFERENCE["finder_container"]` selectors |
| **No bookable buttons found** | Exam slots may not be available yet. Check the page manually and verify the XPath in `SELECTOR_REFERENCE` |
| **Wrong city being targeted** | Check `exam_schedule` dates in your config. The bot targets the nearest upcoming date. Run the bot to see "Exam schedule: targeting X" in logs |
| **Rate-limited / blocked** | Increase `--poll-interval-seconds` (e.g. 90+). The script will auto-cooldown on 429/503 |
| **Desktop notifications not working** | Ensure `plyer` is installed. On Linux, you may need `libnotify` (`sudo apt install libnotify-bin`) |
| **Script crashes during burst** | Normal during high traffic. The script auto-retries every 1.5s |
| **`setup.sh` fails** | Ensure Python 3.9+ is installed. Run `python3 --version` to check |

---

## License

This project is for **personal educational use only**. No license is granted for commercial use or for circumventing website Terms of Service.
