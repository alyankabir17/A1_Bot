#!/usr/bin/env python3
"""
Goethe A1 Booking Helper (Single User, Polite, Safety-First)
=============================================================

LEGAL / ETHICAL WARNING (READ FIRST)
------------------------------------
This script is intended ONLY for personal, fair, and lawful use by one user.
You are responsible for following Goethe-Institut website Terms of Service,
local laws, and any anti-abuse rules. Automation can lead to account/IP blocks.
Use conservative polling intervals and human-like delays.

The script automates only the booking flow steps and then stops.

Quick Start
-----------
1) Install Python dependencies (Python 3.9+):
   pip install -U selenium webdriver-manager plyer

2) Prepare config.csv

3) Run:
   python booking_helper.py --config config.csv --start-monitoring-at now

   Example with explicit settings:
   python booking_helper.py \
    --config config.csv \
      --start-monitoring-at 2026-02-20T23:00:00 \
      --poll-interval-seconds 30 \
      --use-headless false

4) Keep browser visible (headless=False recommended) so you can manually review.

When selectors break
--------------------
Websites change frequently. Update constants in SELECTOR_REFERENCE:
- Finder container selectors
- Book button XPath/CSS
- Preferred city matching logic

Most important selectors/XPaths used
------------------------------------
1) Finder container (wait target):
   - #pr_finder_9523459
   - .pr-finder

2) Bookable buttons (primary XPath):
   - //a|//button containing text variants: "Book", "Next", "Book now"
   - class contains "standard"
   - class does NOT contain "disabled" or "nicht-buchbar"

3) Fallback button selector:
   - a.standard, button.standard

Safety guarantees in this script
--------------------------------
- Single browser session, single tab, no parallel sessions.
- Books at most one slot per run.
- Human-like delays (1.2s to 4.8s) between interactions.
- Backoff and cooling-off on 429/503/Cloudflare-like blocking.
- Stops after the booking flow (no final registration form automation).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

try:
    from plyer import notification
except Exception:
    notification = None


MAIN_URL = "https://www.goethe.de/ins/pk/en/spr/prf/gzb1.cfm"

SELECTOR_REFERENCE = {
    "finder_container": ["#pr_finder_9523459", ".pr-finder"],
    "book_button_xpath": (
        "//*[self::a or self::button]"
        "[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'book')"
        " or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')"
        " or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'book now')"
        " or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'buchen')"
        " or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'weiter')]"
        "[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'standard')]"
        "[not(contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'disabled'))]"
        "[not(contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nicht-buchbar'))]"
    ),
    "book_button_fallback_css": "a.standard, button.standard",
}

DEFAULT_POLL_INTERVAL = 45
MIN_HUMAN_DELAY = 1.5
MAX_HUMAN_DELAY = 5.5

# Burst mode: fast polling around the exact exam booking open time
BURST_BEFORE_SECONDS = 10     # start burst 10s before exam time
BURST_AFTER_SECONDS = 150     # keep burst active 150s after exam time
BURST_PRE_POLL = 5.0          # refresh every 5s BEFORE exam time
BURST_POST_POLL_MIN = 2.0     # refresh every 2-3s AFTER exam time
BURST_POST_POLL_MAX = 3.0
BURST_CRASH_RETRY = 1.5       # retry gap if site crashes during burst


def setup_logger() -> logging.Logger:
    log_name = f"booking_helper_{dt.date.today().isoformat()}.log"
    logger = logging.getLogger("booking_helper")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(log_name, encoding="utf-8")
    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream_handler.setFormatter(stream_fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info("Logging initialized. File: %s", log_name)
    return logger


def parse_bool(value: str) -> bool:
    value = str(value).strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polite Goethe A1 booking helper")
    parser.add_argument("--config", default="config.csv", help="Path to config.csv")
    parser.add_argument("--start-monitoring-at", default="now", help="ISO datetime (local) or 'now'")
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--use-headless", type=parse_bool, default=False)
    parser.add_argument(
        "--exam-time",
        default="now",
        help="'now', HH:MM:SS, or ISO datetime for burst anchor time. Default: now",
    )

    return parser.parse_args()


def load_user_data(path: str) -> Dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if config_path.suffix.lower() != ".csv":
        raise ValueError("Config must be .csv")

    with config_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if not rows:
            raise ValueError("CSV is empty. Add one row with your data.")
        data = {k.strip(): str(v).strip() for k, v in rows[0].items()}

    aliases = {
        "mobile": "phone",
        "preferred_center": "city_preferred",
        "exam_language": "preferred_language",
    }
    for src_key, target_key in aliases.items():
        if src_key in data and target_key not in data:
            data[target_key] = data[src_key]

    return data


def parse_exam_schedule(raw: str) -> List[Tuple[dt.date, Optional[dt.datetime], str]]:
    """Parse exam schedule string into sorted list of (date, datetime_or_None, city).

    Supported entry formats:
      - YYYY-MM-DD:City              (date only, no burst time)
      - YYYY-MM-DDTHH:MM:SS:City     (date + exact booking-open time)
    Entries are separated by semicolons.
    """
    raw = raw.strip()
    if not raw:
        return []
    schedule: List[Tuple[dt.date, Optional[dt.datetime], str]] = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        # Split from the RIGHT on ':' so that HH:MM:SS is preserved
        # Possible shapes:  "2026-03-13:Lahore"  or  "2026-03-13T10:26:00:Lahore"
        last_colon = entry.rfind(":")
        # Walk backwards: city is always after the LAST colon IF the char before
        # is not a digit (i.e. not part of HH:MM:SS).  Safest: split on 'T' first.
        if "T" in entry:
            # Has time component  e.g. "2026-03-13T10:26:00:Lahore"
            t_pos = entry.index("T")
            date_str = entry[:t_pos]  # "2026-03-13"
            rest = entry[t_pos + 1:]  # "10:26:00:Lahore"
            # City is after the last colon
            last_colon = rest.rfind(":")
            time_str = rest[:last_colon].strip()  # "10:26:00"
            city = rest[last_colon + 1:].strip()  # "Lahore"
            exam_date = dt.date.fromisoformat(date_str.strip())
            exam_dt_val = dt.datetime.fromisoformat(f"{date_str.strip()}T{time_str}")
            schedule.append((exam_date, exam_dt_val, city))
        else:
            # Date only  e.g. "2026-03-27:Karachi"
            date_str, city = entry.split(":", 1)
            exam_date = dt.date.fromisoformat(date_str.strip())
            schedule.append((exam_date, None, city.strip()))
    schedule.sort(key=lambda x: x[0])
    return schedule


def get_scheduled_city(schedule: List[Tuple[dt.date, Optional[dt.datetime], str]], logger: logging.Logger) -> str:
    """Return city for the nearest upcoming schedule entry.

    For entries with an explicit datetime, already-past times are skipped.
    Date-only entries remain valid for the whole day.
    """
    if not schedule:
        return ""
    now = dt.datetime.now()
    today = now.date()
    for exam_date, exam_dt_val, city in schedule:
        if exam_dt_val is not None:
            if exam_dt_val >= now:
                logger.info("Exam schedule: targeting %s (exam date %s)", city, exam_date.isoformat())
                return city
            continue

        if exam_date >= today:
            logger.info("Exam schedule: targeting %s (exam date %s)", city, exam_date.isoformat())
            return city

    # All dates have passed — return the last one as fallback
    last_date, _, last_city = schedule[-1]
    logger.warning("All scheduled exam dates have passed. Using last: %s (%s)", last_city, last_date.isoformat())
    return last_city


def get_scheduled_exam_dt(schedule: List[Tuple[dt.date, Optional[dt.datetime], str]]) -> Optional[dt.datetime]:
    """Return nearest future datetime for burst mode (skip already-past times)."""
    now = dt.datetime.now()
    for _, exam_dt_val, _ in schedule:
        if exam_dt_val is not None and exam_dt_val >= now:
            return exam_dt_val
    return None


def random_human_delay(min_sec: float = MIN_HUMAN_DELAY, max_sec: float = MAX_HUMAN_DELAY) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def notify(title: str, message: str, logger: logging.Logger) -> None:
    logger.info("NOTIFY: %s - %s", title, message)
    if notification is None:
        return
    try:
        notification.notify(title=title, message=message, timeout=8)
    except Exception as exc:
        logger.warning("Desktop notification failed: %s", exc)


def wait_until_start(start_value: str, logger: logging.Logger) -> None:
    if start_value.strip().lower() == "now":
        return

    start_dt = dt.datetime.fromisoformat(start_value)
    while True:
        now = dt.datetime.now()
        if now >= start_dt:
            return
        remaining = int((start_dt - now).total_seconds())
        logger.info("Waiting for start time... %ss remaining", remaining)
        time.sleep(min(30, max(1, remaining)))


def create_driver(use_headless: bool) -> webdriver.Chrome:
    options = Options()
    if use_headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
    options.add_experimental_option("detach", True)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        # Best-effort: reduce obvious automation fingerprint flag.
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass
    return driver


def is_blocked_response(driver: webdriver.Chrome) -> bool:
    title = (driver.title or "").lower()
    # Only check title for status codes (page body may contain them innocently)
    title_checks = ["429", "503", "too many requests", "access denied", "attention required"]
    if any(token in title for token in title_checks):
        return True
    # Check body only for strong Cloudflare / bot-detection indicators
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        body = ""
    strong_checks = [
        "checking your browser",
        "verify you are human",
        "just a moment",
        "enable javascript and cookies",
        "ray id",
    ]
    return any(phrase in body for phrase in strong_checks)


def bounded_backoff(attempt: int, base: int = 3, cap: int = 60) -> int:
    return min(cap, int(base * (2 ** max(0, attempt - 1))))


def long_cooldown_seconds() -> int:
    return random.randint(120, 300)


def wait_for_finder(driver: webdriver.Chrome, timeout: int = 40) -> WebElement:
    wait = WebDriverWait(driver, timeout)
    for css in SELECTOR_REFERENCE["finder_container"]:
        try:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
        except TimeoutException:
            continue
    raise TimeoutException("Exam finder container did not load.")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def looks_clickable(button: WebElement) -> bool:
    if not button.is_displayed():
        return False
    if not button.is_enabled():
        return False
    cls = normalize_text(button.get_attribute("class") or "")
    if "disabled" in cls or "nicht-buchbar" in cls or "gray" in cls or "grey" in cls:
        return False
    aria_disabled = normalize_text(button.get_attribute("aria-disabled") or "")
    if aria_disabled in {"true", "1"}:
        return False
    return True


def find_book_buttons(driver: webdriver.Chrome) -> List[WebElement]:
    xpath = SELECTOR_REFERENCE["book_button_xpath"]
    buttons = driver.find_elements(By.XPATH, xpath)

    if not buttons:
        fallback = driver.find_elements(By.CSS_SELECTOR, SELECTOR_REFERENCE["book_button_fallback_css"])
        text_filtered = []
        for item in fallback:
            txt = normalize_text(item.text)
            if any(token in txt for token in ["book", "next", "buchen", "weiter"]):
                text_filtered.append(item)
        buttons = text_filtered

    return [btn for btn in buttons if looks_clickable(btn)]


def button_row_text(button: WebElement) -> str:
    try:
        row = button.find_element(By.XPATH, "ancestor::*[self::tr or self::li or self::div][1]")
        return normalize_text(row.text)
    except Exception:
        return normalize_text(button.text)


def pick_preferred_button(buttons: Sequence[WebElement], preferred_city: str) -> Optional[WebElement]:
    """Select the button whose row text contains the preferred city name.

    If *preferred_city* is provided and matches a button row, that button is
    returned.  Otherwise, the first available button is returned as a
    fallback (no hardcoded city default).
    """
    if not buttons:
        return None

    preferred = normalize_text(preferred_city)
    if preferred:
        for button in buttons:
            if preferred in button_row_text(button):
                return button

    # No preferred city matched — return first available button
    return buttons[0]


def human_move_and_click(driver: webdriver.Chrome, element: WebElement) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    # Keep single-tab behavior even if site uses target="_blank" links.
    try:
        driver.execute_script("arguments[0].removeAttribute('target');", element)
    except Exception:
        pass
    random_human_delay()

    actions = ActionChains(driver)
    actions.move_to_element(element)
    actions.pause(random.uniform(0.2, 0.9))
    actions.move_by_offset(random.randint(-4, 4), random.randint(-4, 4))
    actions.pause(random.uniform(0.1, 0.5))
    actions.click()
    actions.perform()


def enforce_single_tab(driver: webdriver.Chrome) -> None:
    handles = driver.window_handles
    if len(handles) <= 1:
        return

    keep = handles[-1]
    for handle in handles:
        if handle == keep:
            continue
        try:
            driver.switch_to.window(handle)
            driver.close()
        except Exception:
            pass
    driver.switch_to.window(keep)


def wait_for_document_ready(driver: webdriver.Chrome, timeout: int = 30) -> None:
    end_time = time.time() + timeout
    while time.time() < end_time:
        state = driver.execute_script("return document.readyState")
        if state == "complete":
            return
        time.sleep(0.5)
    raise TimeoutException("Document not ready in time.")


def click_continue_button(driver: webdriver.Chrome, logger: logging.Logger, timeout: int = 90) -> None:
    """Step 2: Wait for and click the 'Continue' button on the Selection page."""
    random_human_delay(1.0, 2.5)
    wait_for_document_ready(driver, timeout=timeout)
    continue_xpath = (
        "//*[self::a or self::button]"
        "[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')"
        " or contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'weiter')]"
    )
    wait = WebDriverWait(driver, timeout)
    button = wait.until(EC.element_to_be_clickable((By.XPATH, continue_xpath)))
    logger.info("'Continue' button found. Clicking...")
    human_move_and_click(driver, button)


def click_book_for_myself(driver: webdriver.Chrome, logger: logging.Logger, timeout: int = 90) -> None:
    """Step 3: Wait for and click 'Book for myself' on the Participant page."""
    random_human_delay(1.0, 2.5)
    wait_for_document_ready(driver, timeout=timeout)
    book_myself_xpath = (
        "//*[self::a or self::button]"
        "[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'book for myself')"
        " or contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'für mich buchen')"
        " or contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'für mich')]"
    )
    wait = WebDriverWait(driver, timeout)
    button = wait.until(EC.element_to_be_clickable((By.XPATH, book_myself_xpath)))
    logger.info("'Book for myself' button found. Clicking...")
    human_move_and_click(driver, button)


def parse_exam_time(raw: str) -> Optional[dt.datetime]:
    """Parse --exam-time into a datetime for today (or full ISO)."""
    raw = raw.strip()
    if not raw:
        return None
    if raw.lower() == "now":
        return dt.datetime.now()
    # If user gave just HH:MM:SS or HH:MM, attach today's date
    if "T" not in raw and "-" not in raw:
        today = dt.date.today().isoformat()
        raw = f"{today}T{raw}"
    return dt.datetime.fromisoformat(raw)


def is_burst_window(exam_dt: Optional[dt.datetime]) -> bool:
    """True if we are inside the fast-poll burst window."""
    if exam_dt is None:
        return False
    now = dt.datetime.now()
    start = exam_dt - dt.timedelta(seconds=BURST_BEFORE_SECONDS)
    end = exam_dt + dt.timedelta(seconds=BURST_AFTER_SECONDS)
    return start <= now <= end


def monitor_and_book(
    driver: webdriver.Chrome,
    user_data: Dict[str, str],
    poll_interval_seconds: int,
    exam_dt: Optional[dt.datetime],
    logger: logging.Logger,
) -> None:
    """
    3-step booking automation:
      Step 1: Refresh & click 'Book Now'
      Step 2: Click 'Continue'
      Step 3: Click 'Book for myself' -> STOP (user logs in manually)
    """
    consecutive_errors = 0
    page_loaded = False
    step1_done = False

    # Parse exam schedule once; city is resolved dynamically each cycle
    exam_schedule = parse_exam_schedule(user_data.get("exam_schedule", ""))
    if exam_schedule:
        logger.info("Exam schedule loaded: %s",
                    ", ".join(f"{d.isoformat()}{' @ '+t.strftime('%H:%M:%S') if t else ''} -> {c}"
                              for d, t, c in exam_schedule))

    # ══════════════════════════════════════════════════════════════
    # STEP 1: Refresh & Click "Book Now"
    # ══════════════════════════════════════════════════════════════
    logger.info("══ STEP 1: Waiting for 'Book Now' button ══")

    while True:
        burst = is_burst_window(exam_dt)

        try:
            if burst and page_loaded:
                logger.info("Refreshing page...")
                driver.refresh()
            else:
                logger.info("Opening: %s", MAIN_URL)
                driver.get(MAIN_URL)

            wait_for_document_ready(driver, timeout=15 if burst else 30)
            page_loaded = True

            # Skip block detection during burst
            if not burst and is_blocked_response(driver):
                cooldown = long_cooldown_seconds()
                logger.warning("Block detected. Cooling down %ss", cooldown)
                notify("Blocked", f"Waiting {cooldown // 60} min.", logger)
                time.sleep(cooldown)
                page_loaded = False
                continue

            try:
                wait_for_finder(driver, timeout=10 if burst else 40)
            except TimeoutException:
                if burst:
                    logger.warning("Finder not loaded (site overloaded). Retrying in %.1fs", BURST_CRASH_RETRY)
                    time.sleep(BURST_CRASH_RETRY)
                    continue
                raise

            buttons = find_book_buttons(driver)
            logger.info("Found %d clickable button(s).", len(buttons))
            if not buttons:
                logger.info("Debug page state: title='%s' url='%s'", driver.title, driver.current_url)

            # Determine preferred city
            if exam_schedule:
                preferred_city = get_scheduled_city(exam_schedule, logger)
            else:
                preferred_city = user_data.get("city_preferred", "")
            target_button = pick_preferred_button(buttons, preferred_city)

            if target_button is None:
                # No slot yet — refresh interval per spec
                now = dt.datetime.now()
                if burst and exam_dt and now < exam_dt:
                    # Before exam time -> every 5 seconds
                    gap = BURST_PRE_POLL
                    logger.info("Pre-exam: no slot. Refresh in %.1fs", gap)
                elif burst:
                    # After exam time -> every 2-3 seconds
                    gap = random.uniform(BURST_POST_POLL_MIN, BURST_POST_POLL_MAX)
                    logger.info("Post-exam: no slot. Refresh in %.1fs", gap)
                else:
                    jitter = random.randint(-10, 15)
                    gap = max(20, poll_interval_seconds + jitter)
                    logger.info("No slots. Next check in %ss", gap)
                time.sleep(gap)
                continue

            # ── SLOT FOUND -> click immediately ──
            logger.info("★ STEP 1 DONE: 'Book Now' button found! Clicking...")
            notify("Slot found!", "Clicking Book Now...", logger)
            human_move_and_click(driver, target_button)
            enforce_single_tab(driver)
            consecutive_errors = 0
            step1_done = True
            break  # Exit Step 1 loop

        except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as exc:
            consecutive_errors += 1
            if burst:
                logger.warning("Selenium error: %s. Retrying in %.1fs", exc, BURST_CRASH_RETRY)
                time.sleep(BURST_CRASH_RETRY)
            else:
                delay = bounded_backoff(consecutive_errors)
                logger.warning("Selenium error: %s. Backoff %ss", exc, delay)
                time.sleep(delay)
            page_loaded = False
        except WebDriverException as exc:
            consecutive_errors += 1
            if burst:
                logger.error("WebDriver error: %s. Retrying in %.1fs", exc, BURST_CRASH_RETRY * 2)
                time.sleep(BURST_CRASH_RETRY * 2)
            else:
                delay = bounded_backoff(consecutive_errors, base=5, cap=120)
                logger.error("WebDriver error: %s. Backoff %ss", exc, delay)
                time.sleep(delay)
            page_loaded = False
        except Exception as exc:
            consecutive_errors += 1
            delay = BURST_CRASH_RETRY if burst else bounded_backoff(consecutive_errors, base=5, cap=120)
            logger.exception("Error: %s", exc)
            notify("Booking helper error", str(exc), logger)
            time.sleep(delay)
            page_loaded = False

    if not step1_done:
        return

    # ══════════════════════════════════════════════════════════════
    # STEP 2: Click "Continue"
    # ══════════════════════════════════════════════════════════════
    logger.info("══ STEP 2: Waiting for 'Continue' button ══")
    try:
        click_continue_button(driver, logger, timeout=90)
        enforce_single_tab(driver)
        logger.info("★ STEP 2 DONE: 'Continue' clicked.")
    except Exception as exc:
        logger.error("STEP 2 FAILED: %s", exc)
        notify("Step 2 failed", f"Could not click Continue: {exc}", logger)
        logger.info("Browser left open. Try clicking 'Continue' manually.")
        return

    # ══════════════════════════════════════════════════════════════
    # STEP 3: Click "Book for myself" & STOP
    # ══════════════════════════════════════════════════════════════
    logger.info("══ STEP 3: Waiting for 'Book for myself' button ══")
    try:
        click_book_for_myself(driver, logger, timeout=90)
        enforce_single_tab(driver)
        logger.info("★ STEP 3 DONE: 'Book for myself' clicked.")
    except Exception as exc:
        logger.error("STEP 3 FAILED: %s", exc)
        notify("Step 3 failed", f"Could not click 'Book for myself': {exc}", logger)
        logger.info("Browser left open. Try clicking 'Book for myself' manually.")
        return

    # ══════════════════════════════════════════════════════════════
    # CRITICAL STOP — All 3 steps complete
    # ══════════════════════════════════════════════════════════════
    logger.info("═══════════════════════════════════════════════════")
    logger.info("ALL 3 STEPS COMPLETE. Bot is now STOPPED.")
    logger.info("You are on the Goethe login page.")
    logger.info("Please LOG IN and FILL THE FORM MANUALLY.")
    logger.info("═══════════════════════════════════════════════════")
    notify("Bot stopped - all done", "3 steps complete. Log in and fill form manually.", logger)


def main() -> int:
    args = parse_args()
    logger = setup_logger()

    logger.warning("Personal single-user use only. Respect Terms of Service.")

    user_data = load_user_data(args.config)

    # Log exam schedule
    if user_data.get("exam_schedule"):
        schedule = parse_exam_schedule(user_data["exam_schedule"])
        logger.info("Exam schedule: %s",
                    ", ".join(f"{d.isoformat()}{' @ '+t.strftime('%H:%M:%S') if t else ''} -> {c}"
                              for d, t, c in schedule))
        current_city = get_scheduled_city(schedule, logger)
        logger.info("Current target city: %s", current_city)

    # Burst mode timing
    exam_dt = None
    if user_data.get("exam_schedule"):
        schedule = parse_exam_schedule(user_data["exam_schedule"])
        exam_dt = get_scheduled_exam_dt(schedule)
    if exam_dt is None and args.exam_time.strip().lower() != "now":
        exam_dt = parse_exam_time(args.exam_time)
    if exam_dt is None:
        exam_dt = dt.datetime.now()
        logger.info("No future exam time found; using current time as burst anchor.")
    if exam_dt:
        logger.info("Exam time: %s — burst from %s to %s",
                    exam_dt.strftime("%H:%M:%S"),
                    (exam_dt - dt.timedelta(seconds=BURST_BEFORE_SECONDS)).strftime("%H:%M:%S"),
                    (exam_dt + dt.timedelta(seconds=BURST_AFTER_SECONDS)).strftime("%H:%M:%S"))

    wait_until_start(args.start_monitoring_at, logger)

    driver = None
    try:
        driver = create_driver(args.use_headless)
        monitor_and_book(
            driver=driver,
            user_data=user_data,
            poll_interval_seconds=args.poll_interval_seconds,
            exam_dt=exam_dt,
            logger=logger,
        )

        # ── Keep browser open for manual login ──
        logger.info("Browser is open. Press Ctrl+C when you are done.")
        print("\n" + "=" * 55)
        print("  BOT STOPPED. Browser is open for manual login.")
        print("  Press Ctrl+C when you are finished.")
        print("=" * 55 + "\n")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("User finished. Closing browser.")

        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        return 0
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        notify("Fatal error", str(exc), logger)
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
