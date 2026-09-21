#!/usr/bin/env python3
"""probe3: capture responses of the WIDGET's OWN requests (intercept + click-through)."""
import json
import os
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
    "var self=this;"
    "this.addEventListener('load',function(){"
    "  try{window.__cap.push({m:self.__m,u:self.__u,status:self.status,"
    "    ct:self.getResponseHeader('Content-Type')||'',len:self.responseText.length,"
    "    head:self.responseText.substring(0,500)});}catch(e){}"
    "});"
    "return s1.apply(this,arguments);};}"
)

DUMP_CAP = "return JSON.stringify(window.__cap||[]);"


def dump(drv, label):
    try:
        cap = json.loads(drv.execute_script(DUMP_CAP))
        print(f"== {label}: {len(cap)} captured request(s) ==", flush=True)
        for o in cap:
            print(f"  {o.get('m')} {o.get('u','')[:180]} -> {o.get('status')} "
                  f"{o.get('ct','')[:30]} len={o.get('len')} {json.dumps(o.get('head'))[:240]}",
                  flush=True)
        drv.execute_script("window.__cap=[];")
        return cap
    except Exception as e:
        print(f"dump failed ({label}): {e}", flush=True)
        return []


def main():
    conf = ca.load_conf()
    for attempt in range(1, 4):
        print(f"===== ATTEMPT {attempt}/3 =====", flush=True)
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
            print("gate passed; installing interceptor and reloading", flush=True)
            drv.execute_script(INTERCEPT)
            drv.get(conf["widget_url"])
            time.sleep(12)
            dump(drv, "after reload (widget boot requests)")

            clicks = 0
            for round_no in range(10):
                body = ""
                try:
                    body = drv.find_element(By.TAG_NAME, "body").text[:400]
                except Exception:
                    pass
                print(f"-- round {round_no} body: {body[:160]}", flush=True)
                candidates = []
                try:
                    els = drv.find_elements(By.CSS_SELECTOR,
                        "a, button, input[type=button], input[type=submit], li[onclick], div[onclick]")
                    for el in els:
                        try:
                            tag = el.tag_name
                            txt = (el.text or "").strip()
                            href = el.get_attribute("href") or ""
                            oc = el.get_attribute("onclick") or ""
                            cls = el.get_attribute("class") or ""
                            if not (txt or href or oc):
                                continue
                            candidates.append((el, f"{tag}|{txt[:30]}|{href[:40]}|{cls[:30]}"))
                        except Exception:
                            continue
                except Exception:
                    break
                if not candidates:
                    break
                clicked = False
                for el, label in candidates:
                    try:
                        if el.is_displayed() and el.is_enabled():
                            el.click()
                            print(f"clicked [{label}]", flush=True)
                            clicked = True
                            clicks += 1
                            break
                    except Exception:
                        continue
                if not clicked:
                    break
                time.sleep(6)
                cap = dump(drv, f"after click {clicks}")
                for o in cap:
                    if o.get("u", "").split("/")[-1].split("?")[0] == "datetime/" and o.get("len"):
                        try:
                            import re
                            mm = re.search(r"\((\{.*\})\)", o.get("head") or "")
                            data = json.loads(mm.group(1)) if mm else None
                            slots = ca.parse_slots(data) if data else []
                            print(f"***** datetime response captured: "
                                  f"{len(slots)} slots *****", flush=True)
                            for s in slots[:40]:
                                print(f"  FREE {s['date']} {s['time']}", flush=True)
                            return 0
                        except Exception as e:
                            print(f"datetime parse: {e}", flush=True)
                if clicks > 14:
                    break
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