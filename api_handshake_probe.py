import json, time
import cita_auto

conf = json.load(open("config.json"))
drv = cita_auto.browser_new(conf)
try:
    if not cita_auto.solve_challenge(drv, conf):
        print("gate FAILED", flush=True)
        raise SystemExit(1)
    time.sleep(2)
    session = cita_auto.capture_session(drv, conf)
    print("cookies:", len(session["cookies"]), flush=True)
    api = cita_auto.ApiClient(conf, session)
    cb = "jQuery21105666899906434029_1787235399356"
    base_params = api.base_params()
    qs = api._qs({**base_params, "callback": cb, "_": int(time.time() * 1000)})
    for ep in ("main/", "getwidgetconfigurations/", "getservices/"):
        url = api.base + ep + "?" + qs
        r = api.sess.get(url, headers=api.headers, timeout=25)
        body = r.text.strip()
        print(f"{ep}: status={r.status_code} {len(body)}B :: {body[:180]}", flush=True)
finally:
    cita_auto.quit_driver(drv)
print("DONE", flush=True)