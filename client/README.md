# CITA AUTO - Client Standalone Package

Turnkey, self-contained automated appointment slot monitor and fast auto-booking system for Spanish Consular appointments (Bookitit / citaconsular.es).

---

## 🚀 Quick Start (Windows)

### Method A: 1-Click Runner
1. Double-click **`start.bat`**.
2. An interactive menu appears:
   ```text
   ====================================================================
             CITA AUTO - Consular Appointment Automated System
   ====================================================================
     1. Start Continuous 24/7 Live Auto-Booking (Full Run) [DEFAULT]
     2. Deep Check Applicants & Saved Consular PDF Receipts
     3. Real-Time Slot Monitor (Watch Mode)
     4. Quick Single-Pass Slot Check
     5. Pre-Authenticate & Cache Applicant Tokens
     6. Show Configured Applicants & Status
     7. Exit
   ====================================================================
   ```
3. Press **`Enter`** (or type `1`) to start 24/7 live monitoring and auto-booking.

---

## 🛠️ How to Compile `cita_auto.exe`

If you want a standalone `.exe` binary that runs without needing Python:

1. Double-click **`build_exe.bat`** (or run `python build_exe.py` in your terminal).
2. The script will automatically:
   - Install required packages (`selenium`, `curl_cffi`, `requests`, `pyinstaller`)
   - Compile `cita_auto.exe`
   - Place `cita_auto.exe` right here in your client folder.
3. You can now distribute or run `cita_auto.exe` directly on any Windows machine!

---

## ⚙️ Configuration (`config.json`)

Edit `config.json` in any text editor (Notepad, VS Code):

```json
{
  "accounts": [
    {
      "login": "YOUR_PASSPORT_OR_LOGIN",
      "password": "YOUR_PASSWORD",
      "login_type": "document",
      "profile": {
        "first_name": "Applicant Name",
        "last_name": "Applicant Surname",
        "email": "user@example.com",
        "phone": "000000000",
        "country": "GNB"
      }
    }
  ],
  "date_start": "2026-09-22",
  "date_end": "2027-12-31",
  "poll_interval": 5,
  "auto_book": true,
  "random_slots": true
}
```

- **`accounts`**: Add as many applicants as you need. The bot will authenticate all of them and book distinct free slots simultaneously.
- **`date_start` / `date_end`**: The calendar window you want to accept appointment dates in.
- **`poll_interval`**: Checking speed in seconds (default: `5`).
- **`auto_book`**: Set `true` to immediately book free slots the instant they appear.

---

## 📱 Telegram Live Updates & Alerts (`@CapSpain_bot`)

Your private Telegram bot token is **securely embedded inside the executable** (hidden and protected against code inspection).

### To link your Telegram:
1. Open Telegram and search for **`@CapSpain_bot`** (or visit **[t.me/CapSpain_bot](https://t.me/CapSpain_bot)**).
2. Tap **`/start`**.
3. You will instantly receive a welcome confirmation.

### What the bot does:
- 🟢 **Live Dashboard**: Updates real-time scanning status and current round.
- 🚨 **Instant Slot Discovery**: The millisecond a slot opens, you receive an alert with the available dates and times.
- 🎉 **Full Booking Confirmation**: As soon as an applicant is booked, the bot sends:
  - Applicant **Full Name**
  - **Login ID**
  - **Password**
  - **Booking Date & Time**
  - **Official Consular PDF Receipt** attached directly to the message.
- 💬 **Interactive Commands**:
  - Type **`/status`** or **`/logs`** anytime to get the live scanner status and recent logs.

---

## 📄 Official PDF Receipts

When an appointment is confirmed (either existing or booked new), the system captures the official Bookitit consular receipt and saves it to:
`state/receipts/<login>_<date>_<time>.pdf`
and sends it directly to your Telegram chat.
