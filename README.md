# cita_auto

Automatic appointment booking for the Spanish consular widget (BOOKITIT platform) at
`citaconsular.es` — target: **Embajada de España en República de Guinea Bissau V**
(office publickey `2a6f108852f93a6a84463685beccc087b`).

## Setup

```
pip install selenium curl_cffi
```

`config.json` holds credentials (git-ignored). Fill in the booking profile fields
(first/last name, email, phone) before running `book`.

On Linux, sudo apt-get install chromium / chrome DRIVER may be needed for `book`
mode. The API fast-lane (`check` / `watch`) only needs curl.

## Usage

```
python3 cita_auto.py setup    # solve Cloudflare once, save session to state/
python3 cita_auto.py check    # one-shot availability poll (fast API lane)
python3 cita_auto.py watch    # poll every poll_interval s; auto-book when free
python3 cita_auto.py watch --auto-book   # keep watching; book earliest slot per user until all booked
python3 cita_auto.py book     # ALL accounts in a single browser session
python3 cita_auto.py book --user C00462638   # only that account
python3 cita_auto.py verify   # test every account's login/password; report which conform
python3 cita_auto.py verify --user C00462638
python3 cita_auto.py check --from 2026-08-01 --to 2026-08-31
```

Order matters: run `setup` first so a valid PHPSESSID + cf_clearance pair is saved.
The API lane reuses that session; when it reports `session-invalid` or HTTP 403,
re-run `setup`. `setup` also verifies every configured account against
`signinaccount` and stores the tally in state.

`watch` prints `FREE <date> <time> ...` lines as soon as a slot appears (read-only
mode exits after the first poll that finds slots). With `--auto-book` it instead
keeps watching and books every configured user as soon as slots exist: each poll
assigns the **earliest distinct free slot to each not-yet-booked user** (user1 →
earliest, user2 → next earliest, ...), drives a single browser session (one
Cloudflare solve) that logs in per account and clicks that exact date/time slot,
then marks the user booked in `state/state.json` (`booked_logins` + `last_booked`).
Already-booked users are skipped on every poll and on re-runs, so nobody is
double-booked and remaining users keep picking fresh earliest slots as they
appear; the loop exits 0 once every configured user has a slot. If a slot click
fails, that user stays pending and is retried on the next poll. Client-profile
fields (`first_name`/`last_name`/`email`/`phone`/`passport` in each account's
`profile`) are auto-filled when present, otherwise you must complete the
SMS/email validation step manually (`validate_code_manual`). A screenshot is
saved to `state/watch_final.png`.

`book` defaults to a single session for multiple accounts (`--one-session` forces
it even for one account). `verify` is the fastest way to answer "which user
conforms": it only needs the saved session and hits `signinaccount` per account,
printing `OK` or `FAIL` per login along with the returned token/name.

## Booking chain (from widget source)

Widget route: `/es/hosteds/widgetdefault/<publickey>/#...`
API base: `https://www.citaconsular.es/onlinebookings/` — JSONP (or form POST), all
data merged over `bkt_init_widget`:

```json
{"type":"default","publickey":"2a6f108852f93a6a84463685beccc087b","lang":"es",
 "services":[],"agendas":[],"dates":[],"version":"4",
 "src":"https://www.citaconsular.es/es/hosteds/widgetdefault/<hash>/",
 "srvsrc":"https://www.citaconsular.es"}
```

Endpoints (GET parameter-style for JSONP / POST body for form):

| Step | Endpoint | Key params |
|------|----------|------------|
| init | `getwidgetconfigurations/` | base params |
| list services | `getservices/` | base + `services[]` |
| my appointments | `geteventhistory/` | base |
| availability | `datetime/` | base + `services[]`, `start`=`YYYY-MM-01`, `end`=`YYYY-MM-XX`, `selectedPeople`=1 → `{Slots:[{date,times:{HH:MM:...}}], maxDays}` |
| account login | `signinaccount/` | base + `logintype`=`email`\|`document`, `login`, `password` → `{name,signedin,token/bktToken}` |
| book | `signedin/` / `signupfirstappointment/` | base + `services[]`, `agendas[]`, `date`, `time`, `selectedPeople`, `bktToken`, client fields, optional `gct` |
| confirm | `confirmclient/validate` | base + `bktToken`, `code` (SMS/email), `email`, `cellphone` → `{Valid}` |

Client fields sent with booking: name, passport, email, phone, country, etc. — keys
are `encodeURIComponent`-ed in the client (`views_signup.js getDataToFetch`,
`views_signedin.js fetchData`). Each account in `config.json` can hold its own
`profile`; when booking, `place_browser_booking` uses the account's profile for the
client form fields.

Multiple applicants: config holds an `accounts` array (4 credentials configured).
`book` iterates all accounts. `verify` tests them all.

Notes:
- `captcha=0` in the widget config → no reCAPTCHA/turnstile token required for this
  office (`gct` omitted). Other offices may need it.
- Agendas list comes from `getwidgetconfigurations` (`agendas` array); pick the one
  matching the wanted service before `datetime`.
- `confirmclient` validation code is sent by SMS/email after booking submit; the
  browser flow leaves this to you (manual entry) unless you wire the SMS read.
- Payment is disabled for this office (`payment_enable=false`) — no RedSys step.

## Environment note

On Termux the Xvfb-chromium combination is extremely unstable (Cloudflare re-issues
the challenge on every launch; long browser runs die silently). Prefer running this
tool on a desktop OS. `setup` + `watch` on a desktop keeps a single session alive and
polls cheaply via the API lane (interval 120s by default) without touching the browser.