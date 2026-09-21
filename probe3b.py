#!/usr/bin/env python3
"""probe3b: intercept widget's OWN requests, drive UI clicks (no reload = no re-challenge)."""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cita_auto as ca

INTERCEPT = (
    "if(!window.__cap){window.__cap=[];"
    "var s0=XMLHttpRequest.prototype.open,s1=XMLHttpRequest.prototype.send;"
    "XMLHttpRequest.prototype.open=function(m,u){this.__m=m;this.__u=u;return s0.apply(this,arguments);};"
    "XMLHttpRequest.prototype.send=function(b){"
    "  var self=this;"
    "  this.addEventListener('load',function(){"
    "    try{window.__cap.push({m:self.__m,u:self.__u,status:self.status,"
    "      ct:self.getResponseHeader('Content-Type')||'',len:self.responseText.length,"
    "      head:self.responseText.substring(0,500)});}catch(e){}"
    "  });"
    "  return s1.apply(this,arguments);};"
    "var f0=window.fetch;"
    "window.fetch=function(){var args=arguments;"
    "  var p=f0.apply(this,args);"
    "  p.then(function(r){try{"
    "    var c=r.clone();c.text().then(function(t){"
    "      if(t.length<200000)window.__cap.push({m:'FETCH',u:(args[0]&&args[0].url)||String(args[0]),"
    "        status:r.status,ct:r.headers.get('content-type')||'',len:t.length,head:t.substring(0,500)});"
    "    });}catch(e){});"
    "  return p;};}"
)

DUMP_CAP = "return JSON.stringify(window.__cap||[]);"

PRIORITY_TEXT = ("CONTINUAR", "ACEITAR", "ACEPTAR", "AGENDAR", "SOLICITUD", "SIGUIENTE", "OK", "YES", "NO IGUAL", "REAGENDAR")


def dump(drv, label):
    try:
        cap = json.loads(drv.execute_script(DUMP_CAP))
        print(f"== {label}: {len(cap)} request(s) ==", flush=True)
        for o in cap:
            print(f"  {o.get('m')} {o.get('u','')[:170]} -> {o.get('status')} "
                  f"{(o.get('ct') or '')[:28]} len={o.get('len')} head={json.dumps(o.get('head'))[:230]}",
                  flush=True)
        drv.execute_script("window.__cap=[];")
        return cap
    except Exception as e:
        print(f"dump failed ({label}): {e}", flush=True)
        return []


def main():
    conf = ca.load_conf()
    for attempt in range(1, 5):
        print(f"===== ATTEMPT {attempt}/4 =====", flush=True)
        drv = None
        try:
            drv = ca.browser_new(conf)
            if not ca.solve_challenge(drv, conf):
                continue
            ca.capture_session(drv, conf)
            from selenium.webdriver.common.by import By
            ok_gate = False
            for g in range(3):
                try:
                    btn = drv.find_element(By.ID, "idCaptchaButton")
                except Exception:
                    ok_gate = True
                    break
                try:
                    btn.click()
                except Exception:
                    pass
                time.sleep(4)
                try:
                    drv.find_element(By.ID, "idCaptchaButton")
                except Exception:
                    ok_gate = True
                    break
            if not ok_gate:
                print("gate not passed", flush=True)
                continue
            print("gate passed, page booted; installing interceptors (NO reload)", flush=True)
            drv.execute_script(INTERCEPT)

            clicks = 0
            for round_no in range(16):
                candidates = []
                try:
                    els = drv.find_elements(By.CSS_SELECTOR,
                        "a, button, input[type=button], input[type=submit], "
                        "li[onclick], div[onclick], span[onclick], input[type=radio]")
                    for el in els:
                        try:
                            txt = (el.text or "").strip()
                            val = el.get_attribute("value") or ""
                            href = el.get_attribute("href") or ""
                            cls = el.get_attribute("class") or ""
                            if not (txt or href or (val and el.get_attribute("type") == "radio")):
                                continue
                            if "cloudflare.com" in href or "challenges.cloudflare" in href:
                                continue
                            score = 0
                            u = (txt + " " + val).upper()
                            for p in PRIORITY_TEXT:
                                if p in u:
                                    score += 2
                            if "SOLICITUD" in cls.upper() or "agenda" in cls.lower():
                                score += 1
                            candidates.append((score, el, f"{el.tag_name}|{txt[:34]}|{val[:16]}|{cls[:24]}"))
                        except Exception:
                            continue
                except Exception:
                    break
                candidates.sort(key=lambda c: -c[0])
                if not candidates:
                    print("no clickable elements; stopping click loop", flush=True)
                    break
                clicked = False
                for score, el, label in candidates:
                    try:
                        if el.is_displayed() and el.is_enabled():
                            el.click()
                            clicks += 1
                            print(f"click {clicks} [{label}]", flush=True)
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    print("nothing enabled/visible; stopping", flush=True)
                    break
                time.sleep(5)
                cap = dump(drv, f"after click {clicks}")
                for o in cap:
                    u = o.get("u", "")
                    base = u.split("?")[0].rstrip("/")[-40:]
                    head = o.get("head") or ""
                    if "datetime" in u and o.get("len"):
                        print("***** DATETIME RESPONSE *****", flush=True)
                        try:
                            mm = re.search(r"\(\s*(\{.*\})\s*\)", head, re.S)
                            data = json.loads(mm.group(1)) if mm else None
                            slots = ca.parse_slots(data) if data else []
                            print(f"parsed {len(slots)} slot(s):", flush=True)
                            for s in slots[:50]:
                                print(f"  FREE {s['date']} {s['time']}", flush=True)
                            return 0
                        except Exception as e:
                            print(f"datetime parse: {e}", flush=True)
                    if o.get("len") is None and u:
                        print(f"  (no length for {base})", flush=True)
        except Exception as e:
            print(f"attempt {attempt} crashed: {type(e).__name__}: {e}", flush=True)
        finally:
            if drv is not None:
                try:
                    ca.quit_driver(drv)
                except Exception:
                    pass
    print("no datetime response captured", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())