# Goethe A1 Booking Helper Bot

A Selenium-based automation tool that monitors the [Goethe-Institut Pakistan](https://www.goethe.de/ins/pk/en/spr/prf/gzsd1.cfm) exam booking page for available **Goethe-Zertifikat A1** slots, and pre-fills the registration form on your behalf. The script **never auto-submits** — it hands control back to you for final review.

---

## Table of Contents

- [Disclaimer](#disclaimer)
- [Features](#features)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [CSV Format (Recommended)](#csv-format-recommended)
  - [JSON Format](#json-format)
  - [Configuration Fields](#configuration-fields)
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
> - The script intentionally **does NOT auto-submit** the final registration form — it only monitors and pre-fills fields, then hands control back to you.
> - Use conservative polling intervals and human-like delays at all times.

---

## Features

| Feature | Description |
|---|---|
| **Slot Monitoring** | Continuously polls the Goethe exam finder page for bookable slots |
| **City Preference** | Prioritises your preferred exam center (defaults to Islamabad) |
| **Auto Form Fill** | Pre-fills registration fields (name, passport, DOB, email, phone, etc.) |
| **Burst Mode** | Fast-polls around the exact booking-open time for maximum responsiveness |
| **Human-Like Behavior** | Randomised delays (1.5 – 5.5s), mouse jitter, and natural click patterns |
| **Anti-Block Detection** | Detects 429/503/Cloudflare challenges and backs off with cooling periods |
| **Desktop Notifications** | Sends OS-level alerts via `plyer` when a slot is found or errors occur |
| **Single-Tab Enforcement** | Prevents the browser from opening multiple tabs |
| **No Auto-Submit** | Final submit button is highlighted but **never clicked** — you stay in control |
| **File Upload Prompt** | Interactive prompt for passport photo/signature uploads when detected |
| **Structured Logging** | Logs every action to both console and a daily log file |
| **Flexible Config** | Supports both CSV and JSON configuration files |

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
│  Open Goethe exam  │◄──────────────┐
│  finder page       │               │
└────────┬───────────┘               │
         │                           │
         ▼                           │
┌────────────────────┐     No        │
│  Detect clickable  ├──────────────►│
│  "Book" buttons?   │   (sleep/poll)│
└────────┬───────────┘               │
         │ Yes                       │
         ▼                           │
┌────────────────────┐               │
│  Click preferred   │               │
│  city slot         │               │
└────────┬───────────┘               │
         │
         ▼
┌────────────────────┐
│  Pre-fill form     │
│  fields            │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  STOP — User       │
│  reviews & submits │
│  manually          │
└────────────────────┘
```

---

## Prerequisites

- **Python 3.9+**
- **Google Chrome** (installed on  your system)
- **ChromeDriver** — managed automatically by `webdriver-manager`
- **Linux / macOS** (Windows works too, but `setup.sh` is bash-only)

---

## Installation

### Quick Setup (Linux / macOS)

```bash
git clone https://github.com/<your-username>/A1_Bot.git
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

The bot reads your personal data from a config file to auto-fill the registration form. **Two formats** are supported.

### CSV Format (Recommended)

Create a `config.csv` file:

```csv
full_name,passport_number,date_of_birth,gender,nationality,email,phone,city_preferred,preferred_language
John Doe,AB1234567,15/08/2000,Male,Pakistan,john@example.com,+923001234567,Islamabad,English
```

### JSON Format

Create a `config.json` file:

```json
{
  "full_name": "John Doe",
  "passport_number": "AB1234567",
  "date_of_birth": "15/08/2000",
  "gender": "Male",
  "nationality": "Pakistan",
  "email": "john@example.com",
  "mobile": "+923001234567",
  "preferred_center": "Islamabad",
  "exam_language": "English"
}
```

### Configuration Fields

| Field | Required | Description | Aliases |
|---|---|---|---|
| `full_name` | **Yes** | Your full legal name | — |
| `email` | **Yes** | Contact email address | — |
| `passport_number` | No | Passport / ID number | — |
| `date_of_birth` | No | Date of birth (DD/MM/YYYY) | — |
| `gender` | No | Male / Female / Other | — |
| `nationality` | No | Your nationality | — |
| `phone` | No | Phone number with country code | `mobile` |
| `city_preferred` | No | Preferred exam center (e.g. Islamabad) | `preferred_center` |
| `preferred_language` | No | Exam language (e.g. English) | `exam_language` |

> **Note:** The JSON format supports aliases (`mobile` → `phone`, `preferred_center` → `city_preferred`, `exam_language` → `preferred_language`) so you can use either naming convention.

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

When you know exactly when slots open, use `--exam-time` for aggressive fast-polling around that window:

```bash
python booking_helper.py \
  --config config.csv \
  --start-monitoring-at now \
  --exam-time 12:06:00
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
| `--config` | `config.csv` | Path to `config.csv` or `config.json` |
| `--start-monitoring-at` | `now` | ISO datetime (local) or `now` |
| `--poll-interval-seconds` | `45` | Seconds between each poll cycle |
| `--use-headless` | `false` | Run Chrome in headless mode |
| `--exam-time` | *(disabled)* | `HH:MM:SS` or ISO datetime — enables burst mode |

---

## Architecture & Key Components

```
A1_Bot/
├── booking_helper.py   # Main script (all logic)
├── config.csv          # User data (CSV format)
├── config.json         # User data (JSON format)
├── requirements.txt    # Python dependencies
├── setup.sh            # One-command environment setup
├── jenkinsfile         # CI/CD pipeline definition
└── README.md           # This file
```

### Core Functions

| Function | Purpose |
|---|---|
| `load_user_data()` | Parses CSV/JSON config with field aliases |
| `create_driver()` | Launches Chrome with anti-detection flags |
| `monitor_and_book()` | Main polling loop with burst mode support |
| `wait_for_finder()` | Waits for the exam finder widget to load |
| `find_book_buttons()` | Locates clickable "Book" / "Next" buttons via XPath + CSS fallback |
| `pick_preferred_button()` | Selects the button matching your preferred city |
| `human_move_and_click()` | Scrolls, moves mouse with jitter, and clicks |
| `fill_registration_form()` | Auto-fills form fields, skips submit |
| `is_blocked_response()` | Detects Cloudflare / rate-limit pages |
| `is_burst_window()` | Checks if current time is within burst window |
| `notify()` | Sends desktop notification via plyer |

---

## Safety & Anti-Detection Measures

The script is designed to be **polite and undetectable**:

1. **Single Session** — One browser, one tab, no parallel sessions
2. **One Slot Per Run** — Stops after finding and pre-filling one slot
3. **Human-Like Delays** — Random pauses (1.5–5.5s) between every interaction
4. **Mouse Jitter** — Small random offsets on mouse movements
5. **Backoff on Errors** — Exponential backoff (3s base, 60s cap) on failures
6. **Rate-Limit Detection** — Detects 429/503 responses and cools down for 2–5 minutes
7. **Cloudflare Detection** — Identifies "checking your browser" and similar pages
8. **Anti-Automation Flags** — `--disable-blink-features=AutomationControlled`
9. **No Auto-Submit** — The submit button is highlighted in orange but never clicked
10. **Graceful Shutdown** — Handles `Ctrl+C` cleanly, closes browser on exit

---

## Selector Reference

If the Goethe website changes its HTML structure, update these constants in `booking_helper.py`:

| Constant | Current Value | Purpose |
|---|---|---|
| `finder_container` | `#pr_finder_9523459`, `.pr-finder` | Exam finder widget container |
| `book_button_xpath` | XPath matching "Book"/"Next"/"Book now" with class `standard` | Primary button selector |
| `book_button_fallback_css` | `a.standard, button.standard` | Fallback button selector |
| `file_input_css` | `input[type='file']` | File upload fields |
| `submit_buttons_css` | `button[type='submit'], input[type='submit'], .submit, .btn-submit` | Submit buttons (never clicked) |

Form fields are matched using `FORM_FIELD_CANDIDATES` (CSS selectors by field name) and `LABEL_KEYWORDS` (label text matching as fallback).

---

## Logging

The script creates a daily log file named `booking_helper_YYYY-MM-DD.log` in the working directory. All actions, warnings, and errors are logged to both the file and stdout.

Example log output:

```
2026-02-21 12:06:01,234 [INFO] Opening monitor page: https://www.goethe.de/ins/pk/en/spr/prf/gzsd1.cfm
2026-02-21 12:06:05,891 [INFO] BURST: Found 2 clickable button(s).
2026-02-21 12:06:06,123 [INFO] Bookable slot detected! Clicking now.
2026-02-21 12:06:12,456 [INFO] Filled field: full_name
2026-02-21 12:06:14,789 [INFO] Filled field: email
2026-02-21 12:06:16,012 [INFO] Form fill completed. Final submit intentionally NOT clicked.
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
| **Rate-limited / blocked** | Increase `--poll-interval-seconds` (e.g. 90+). The script will auto-cooldown on 429/503 |
| **Fields not being filled** | Update `FORM_FIELD_CANDIDATES` CSS selectors or `LABEL_KEYWORDS` to match current form |
| **Desktop notifications not working** | Ensure `plyer` is installed. On Linux, you may need `libnotify` (`sudo apt install libnotify-bin`) |
| **Script crashes during burst** | Normal during high traffic. The script auto-retries every 1.5s |
| **`setup.sh` fails** | Ensure Python 3.9+ is installed. Run `python3 --version` to check |

---

## License

This project is for **personal educational use only**. No license is granted for commercial use or for circumventing website Terms of Service.
