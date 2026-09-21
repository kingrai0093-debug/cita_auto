import json, time
import cita_auto

conf = json.load(open("config.json"))
drv = cita_auto.browser_new(conf)
try:
    ok = cita_auto.solve_challenge(drv, conf)
    print("gate ok:", ok, flush=True)
    time.sleep(8)
    body = drv.find_element("tag name", "body").text[:600].replace("\n", " | ")
    print("BODY:", body, flush=True)
    res = drv.execute_script(
        "return JSON.stringify(performance.getEntriesByType('resource')"
        ".map(function(r){return r.name})"
        ".filter(function(u){return u.indexOf('onlinebookings')>=0}))")
    print("API RESOURCES:", res[:600], flush=True)
    cookies = drv.get_cookies()
    print("COOKIES:", [(c["name"], c.get("httpOnly")) for c in cookies], flush=True)
    ls = drv.execute_script(
        "var o={};for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);"
        "o[k]=localStorage.getItem(k).slice(0,60)}return JSON.stringify(o)")
    print("LOCALSTORAGE:", ls[:300], flush=True)
finally:
    cita_auto.quit_driver(drv)
print("DONE", flush=True)