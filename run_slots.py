#!/usr/bin/env python3
"""Full-request browserless-look slot probe for cita_auto.

Drives ONE invisible Xvfb browser session (no visible window) to:
  1. pass the Cloudflare challenge + captcha gate (refresh the PHP session)
  2. ensure the widget boots (bkt/jq true) so the API is unlocked
  3. full booking-API chain IN-PAGE (same-origin, exactly like the widget):
       main/ -> getwidgetconfigurations/ -> getservices/ -> datetime/ -> signinaccount/
  4. report the earliest available slots (date/time sorted).

Read-only: never submits a booking.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cita_auto as ca


def main():
    conf = ca.load_conf()
    drv = ca.browser_new(conf)
    try:
        if not ca.solve_challenge(drv, conf):
            print("CF challenge FAILED - see logs", flush=True)
            return 1

        boot_ok = False
        diag = {}
        for attempt in range(4):
            time.sleep(2)
            try:
                diag = json.loads(drv.execute_script(
                    "return JSON.stringify({bkt:(typeof bkt_init_widget!=='undefined'),"
                    "jq:(typeof window.jQuery!=='undefined'),"
                    "ov:(typeof oClientValues_248295!=='undefined')})"))
            except Exception as e:
                print(f"boot check err: {e}", flush=True)
            print(f"boot status: {json.dumps(diag)}", flush=True)
            if diag.get("bkt") and diag.get("jq"):
                boot_ok = True
                break
            if attempt < 3:
                print(f"widget not booted yet; reloading ({attempt + 1}/3)", flush=True)
                try:
                    ca.accept_alert_any(drv)
                except Exception:
                    pass
                drv.get(conf["widget_url"])
                time.sleep(8)
        if not boot_ok:
            print("WARNING: widget JS never booted; API lane may answer "
                  "'Contact with your technical support'.", flush=True)

        api = ca.ApiBrowser(drv, conf)

        print("== [1/5] getwidgetconfigurations ==", flush=True)
        cfg = api.getwidgetconfigurations()
        ok, why = ca.prove_session(cfg)
        print(f"prove_session: ok={ok} why={why}", flush=True)
        print("raw:", json.dumps(cfg)[:600], flush=True)
        if not ok:
            print("API lane rejected; cannot continue.", flush=True)
            return 1

        print("== [2/5] getservices ==", flush=True)
        svc = api.getservices()
        print("raw:", json.dumps(svc)[:600], flush=True)

        print("== [3/5] datetime (configured window) ==", flush=True)
        avail = api.datetime(conf["date_start"], conf["date_end"])
        slots = ca.parse_slots(avail)
        print(f"slots in {conf['date_start']}..{conf['date_end']}: {len(slots)}", flush=True)
        for s in slots[:60]:
            print(f"  FREE {s['date']} {s['time']}", flush=True)
        if avail.get("_error") or avail.get("_raw"):
            print("raw head:", json.dumps(avail)[:400], flush=True)

        print("== [4/5] datetime (wide window Jul..Dec 2026) ==", flush=True)
        wide = api.datetime("2026-07-01", "2026-12-31")
        wslots = ca.parse_slots(wide)
        print(f"slots in 2026-07-01..2026-12-31: {len(wslots)}", flush=True)
        for s in wslots[:60]:
            print(f"  FREE {s['date']} {s['time']}", flush=True)
        if wide.get("_error") or wide.get("_raw"):
            print("raw head:", json.dumps(wide)[:400], flush=True)

        print("== [5/5] signinaccount (every configured account) ==", flush=True)
        for acc in ca.self_accounts(conf, None):
            r = api.getaccountdata(acc)
            if isinstance(r, dict) and r.get("_error"):
                print(f"  {acc['login']}: {r['_error']}", flush=True)
            else:
                name = r.get("name") or r.get("Client") or r.get("client") if isinstance(r, dict) else r
                err = r.get("errors") if isinstance(r, dict) else None
                if err:
                    print(f"  {acc['login']}: FAIL {json.dumps(err)[:120]}", flush=True)
                else:
                    print(f"  {acc['login']}: signin OK {json.dumps(name)[:80]}", flush=True)

        if wslots or slots:
            earliest = (wslots if wslots else slots)[0]
            print(f"EARLIEST SLOT: {earliest['date']} {earliest['time']}", flush=True)
        else:
            print("NO FREE SLOTS in either window", flush=True)

        try:
            drv.save_screenshot(os.path.join(ca.STATE_DIR, "slots_probe.png"))
        except Exception:
            pass
        return 0
    finally:
        ca.quit_driver(drv)


if __name__ == "__main__":
    sys.exit(main())