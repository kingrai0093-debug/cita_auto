# CITA AUTO - Client Standalone Package

Turnkey, self-contained automated appointment slot monitor and fast auto-booking system for Spanish Consular appointments (Bookitit / citaconsular.es).

This client distribution is a **pre-compiled, standalone binary package**. It does **not** require installing Python, compilers, or any external development tools.

---

## 📁 Package Contents

- **`cita_auto.exe`**: Pre-compiled standalone executable bot.
- **`start.bat`**: 1-click Windows launcher.
- **`config.json`**: Configuration file with your applicant logins, passwords, and preferences.
- **`config.example.json`**: Template configuration file for reference.

---

## 🚀 Quick Start (Windows)

1. Extract all files into the same folder.
2. Edit **`config.json`** with your applicant credentials and desired booking dates.
3. Double-click **`start.bat`** (or double-click **`cita_auto.exe`** directly).
4. An interactive launcher menu will appear:
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
5. Press **`Enter`** (or type `1`) to start 24/7 continuous slot monitoring and auto-booking.

---

## ⚙️ Configuration (`config.json`)

Open `config.json` in any text editor (Notepad, VS Code, etc.):

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

- **`accounts`**: Add as many applicants as you need. The system will authenticate each applicant and book available slots simultaneously.
- **`date_start` / `date_end`**: The date range in which you want to book appointments (`YYYY-MM-DD`).
- **`poll_interval`**: Checking interval in seconds (default: `5`).
- **`auto_book`**: Set to `true` to immediately book appointments the millisecond a slot opens.
- **`random_slots`**: Randomize slot selection when multiple slots appear at once.

---

## 📱 Telegram Live Updates & Alerts (`@CapSpain_bot`)

Your private Telegram bot token is **securely embedded inside the executable binary** (hidden and protected against tampering).

### To link your Telegram:
1. Open Telegram and search for **`@CapSpain_bot`** (or visit **[t.me/CapSpain_bot](https://t.me/CapSpain_bot)**).
2. Tap **`/start`**.
3. You will instantly receive a welcome notification.

### Features:
- 🟢 **Live Dashboard**: Displays real-time round counts, active applicants, and health metrics.
- 🚨 **Instant Slot Discovery**: Alerts with available dates and times the instant a slot opens.
- 🎉 **Full Booking Notification**: When an appointment is booked, the bot sends:
  - Applicant **Full Name**
  - **Login ID**
  - **Password**
  - **Booking Date & Time**
  - **Official Consular PDF Receipt** attached directly to the message.
- 💬 **Interactive Commands**:
  - Type **`/status`** or **`/logs`** anytime to get the live scanner status and recent activity logs.

---

## 📄 Official Consular Receipts

When an appointment is confirmed (existing or freshly booked), the system downloads the official consular receipt and saves it to:
```text
state/receipts/<login>_<date>_<time>.pdf
```
It is also automatically sent to your Telegram chat.
