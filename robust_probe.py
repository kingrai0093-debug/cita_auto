#!/usr/bin/env python3
"""Robust probe: retry browser session until booted; then full API chain.

Lanes in order per attempt:
  1. in-page (same-origin XHR) full chain - main/config/services/datetime/signin
  2. external (curl_cffi + exact browser UA) full chain with the saved session

The gate POST ("Continue") marks the PHP session booted server-side; the session
is saved BEFORE the click so a browser crash never loses the tokens.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cita_auto as ca

WIDE = ("2026-07-01", "2026-12-31")


def boot_diag(drv):
    try:
        return json.loads(drv.execute_script(
            "return JSON.stringify({bkt:(typeof bkt_init_widget!=='undefined'),"
            "jq:(typeof window.jQuery!=='undefined')})"))
    except Exception:
        return {}


def click_gate(drv, conf, logfn):
    from selenium.webdriver.common.by import By
    for attempt in range(3):
        try:
            btn = drv.find_element(By.ID, "idCaptchaButton")
        except Exception:
            return True
        try:
            btn.click()
            logfn(f"gate: clicked Continue ({attempt + 1})")
        except Exception as e:
            logfn(f"gate: click failed {e}")
            return False
        time.sleep(4)
        try:
            drv.find_element(By.ID, "idCaptchaButton")
        except Exception:
            logfn("gate: passed, widget page served")
            return True
    return False


def dump_widget(drv, logfn):
    try:
        info = drv.execute_script(
            "var BIW=(typeof bkt_init_widget!=='undefined')?bkt_init_widget:null;"
            "var s={biw:'-',res:'[]'};"
            "if(BIW){try{s.biw=JSON.stringify(BIW).substring(0,3000);}catch(e){s.biw='unserializable';}}"
            "var res=performance.getEntriesByType('resource').map(function(e){return e.name})"
            ".filter(function(u){return u.indexOf('onlinebookings')>=0});"
            "s.res=JSON.stringify(res);return JSON.stringify(s);")
        d = json.loads(info)
        logfn("bkt_init_widget: " + (d.get("biw") or "-")[:3000])
        for u in json.loads(d.get("res") or "[]"):
            logfn("  boot resource: " + u[:220])
    except Exception as e:
        logfn(f"widget dump failed: {e}")


def inpage_lane(drv, conf, logfn):
    api = ca.ApiBrowser(drv, conf)
    results = {}
    cfg = api.getwidgetconfigurations()
    ok, why = ca.prove_session(cfg)
    logfn(f"in-page getwidgetconfigurations: ok={ok} why={why} raw={json.dumps(cfg)[:200]}")
    if not ok:
        results["cfg_ok"] = False
        return results, False
    results["cfg_ok"] = True
    svc = api.getservices()
    logfn("in-page getservices: " + json.dumps(svc)[:200])
    results["services"] = svc
    for label, (start, end) in (("conf", (conf["date_start"], conf["date_end"])), ("wide", WIDE)):
        avail = api.datetime(start, end)
        slots = ca.parse_slots(avail)
        logfn(f"in-page datetime {label} {start}..{end}: {len(slots)} slots "
              f"{'' if slots else json.dumps(avail)[:200]}")
        for s in slots[:50]:
            logfn(f"  FREE {s['date']} {s['time']}")
        results[label + "_slots"] = slots
    for acc in ca.self_accounts(conf, None):
        r = api.getaccountdata(acc)
        err = r.get("errors") if isinstance(r, dict) else None
        logfn(f"in-page signin {acc['login']}: "
              f"{'FAIL '+json.dumps(err)[:100] if err else 'OK '+json.dumps(r.get('name'))[:60]}")
    return results, True


def external_lane(conf, session, logfn):
    try:
        from curl_cffi import requests as cr
        s = cr.Session(impersonate="chrome136")
        s.headers["User-Agent"] = session.get("ua", "")
    except Exception:
        logfn("curl_cffi unavailable for external lane")
        return {}, False
    for c in session.get("cookies", []):
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", "www.citaconsular.es"))
    h = {"Referer": conf["widget_url"], "Accept": "*/*"}
    cb = "jQuery21105666899906434029_1787235399356"
    wp = {"type": "default", "publickey": conf["office_hash"], "lang": conf.get("lang", "es"),
          "version": "4", "src": conf["widget_url"], "callback": cb}
    bp = dict(wp)
    bp.update({"services": [], "agendas": [], "dates": [],
               "srvsrc": "https://www.citaconsular.es"})
    qs = lambda p: "&".join(f"{k}={v}" for k, v in p.items())
    now = int(time.time() * 1000)

    def get(ep, p):
        p = dict(p)
        p["_"] = now
        try:
            r = s.get(conf["api_base"] + ep + "?" + qs(p), headers=h, timeout=25)
        except Exception as e:
            return {"_error": str(e)}
        txt = r.text.strip()
        if not txt:
            return {"_empty": True, "status": r.status_code}
        return txt

    results = {}
    for ep in ("main/", "getwidgetconfigurations/"):
        t = get(ep, wp)
        logfn(f"external {ep}: {str(t)[:200]}")
        results[ep] = t
    cfg = get("getwidgetconfigurations/", bp)
    if isinstance(cfg, dict) and cfg.get("_empty"):
        logfn("external lane: server answers EMPTY for cfg - software hook needed")
        return results, False
    p = dict(wp)
    p["services"] = conf["service_ids"]
    p["start"] = conf["date_start"]
    p["end"] = conf["date_end"]
    p["selectedPeople"] = 1
    t = get("datetime/", p)
    logfn("external datetime: " + str(t)[:260])
    if isinstance(t, str) and t.startswith(cb + "("):
        try:
            data = json.loads(t[len(cb) + 1:-2])
            slots = ca.parse_slots(data)
            logfn(f"external datetime: {len(slots)} slots")
            for s in slots[:50]:
                logfn(f"  FREE {s['date']} {s['time']}")
            results["ext_slots"] = slots
        except Exception as e:
            logfn(f"external datetime parse failed: {e}")
    return results, bool(results.get("ext_slots"))


def main():
    conf = ca.load_conf()
    for attempt in range(1, 5):
        print(f"===== ATTEMPT {attempt}/4 =====", flush=True)
        drv = None
        saved_session = None
        try:
            drv = ca.browser_new(conf)
            if not ca.solve_challenge(drv, conf):
                print("challenge failed", flush=True)
                continue
            saved_session = ca.capture_session(drv, conf)
            print(f"session saved ({len(saved_session['cookies'])} cookies)", flush=True)
            if not click_gate(drv, conf, print):
                print("gate not passed; retrying", flush=True)
                continue
            dump_widget(drv, print)
            boot = boot_diag(drv)
            print("boot: " + json.dumps(boot), flush=True)

            print("--- lane 1: in-page full chain ---", flush=True)
            try:
                res1, ok1 = inpage_lane(drv, conf, print)
            except Exception as e:
                print(f"in-page lane crashed: {type(e).__name__}: {e}", flush=True)
                ok1 = False
            if ok1:
                print(f"IN-PAGE LANE OK; earliest "
                      f"{res1.get('conf_slots') or res1.get('wide_slots', [{}])[0]}", flush=True)
                return 0

            print("--- lane 2: external with saved session ---", flush=True)
            if saved_session:
                res2, ok2 = external_lane(conf, saved_session, print)
                if ok2:
                    print("EXTERNAL LANE OK", flush=True)
                    return 0
        except Exception as e:
            print(f"attempt {attempt} crashed: {type(e).__name__}: {e}", flush=True)
        finally:
            if drv is not None:
                try:
                    ca.quit_driver(drv)
                except Exception:
                    pass
        time.sleep(3)
    print("ALL ATTEMPTS FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())