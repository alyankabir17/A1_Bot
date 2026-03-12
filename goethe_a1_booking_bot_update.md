# Goethe A1 Booking Bot Update (booking_helper.py)

## Objective

Refactor `booking_helper.py` to automate exactly three specific
navigation steps for the Goethe A1 exam booking, and then completely
halt execution so the user can manually log in and fill out the form.

**Target URL:** https://www.goethe.de/ins/pk/en/spr/prf/gzsd1.cfm\
**Target Time:** 10:26 AM (Pakistan Time) on March 13

------------------------------------------------------------------------

# Required 3-Step Automation Flow

## Step 1 --- Refresh & Click "Book Now"

-   Open the Goethe A1 booking page.
-   Begin refresh logic **5--10 seconds before 10:26 AM**.
-   If the **Book** button is not visible:
    -   **Before 10:26 AM → refresh every 5 seconds**
    -   **After 10:26 AM → refresh every 2--3 seconds**
-   Once the **Book** button appears, click it.

------------------------------------------------------------------------

## Step 2 --- Click "Continue"

After clicking **Book**, the website loads the **Selection page**
showing exam details.

The bot must: 1. Wait for the page to load. 2. Locate the **Continue**
button. 3. Click **Continue**.

Use **explicit waits** because the server may be slow during booking
time.

------------------------------------------------------------------------

## Step 3 --- Click "Book for myself" & STOP

After clicking **Continue**, the **Participant page** appears.

The bot must: 1. Locate the **Book for myself** button. 2. Click the
button.

This redirects to the **Goethe login page**.

### CRITICAL STOP

At this point the bot must:

-   Completely **stop execution**
-   **Disable any autofill**
-   **Disable login automation**
-   The user will **manually log in and fill the form**.


