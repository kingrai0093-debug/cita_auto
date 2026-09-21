#!/usr/bin/env python3
import json, re, sys, time
sys.path.insert(0, ".")
import cita_auto

conf = json.load(open("config.json"))
drv = cita_auto.browser_new(conf)
try:
    if not cita_auto.solve_challenge(drv, conf):
        print("CHALLENGE-FAILED")
        raise SystemExit(1)
    time.sleep(4)
    url = drv.current_url
    title = drv.title or ""
    body = drv.find_element("tag name", "body").text[:500].replace("\n", " | ")
    scripts = drv.execute_script(
        "return Array.prototype.slice.call(document.scripts).map(function(x){return x.src})")
    boot = drv.execute_script(
        "var s=Array.prototype.slice.call(document.scripts).map(function(x){return x.src})"
        ".filter(function(u){return u.indexOf('loadermaec')>=0||u.indexOf('mainv1')>=0});"
        "return JSON.stringify({bkt:(typeof bkt_init_widget!=='undefined'),"
        "jq:(typeof window.jQuery!=='undefined'),ov:(typeof oClientValues_248295!=='undefined'),bootscripts:s})")
    print("URL:", url[:160])
    print("TITLE:", title[:100])
    print("BODY:", body)
    print("BODY_HAS_JUST_A_MOMENT:", "Just a moment" in body)
    print("SCRIPTS:", json.dumps(scripts)[:400])
    print("BOOT:", boot)
    html = drv.page_source
    print("HTML_CLASS_HINT:", re.findall(r'(cf-[\w-]+|challenge-[a-z-]*|error-code)', html, re.I)[:8])
    print("ID_BKT_PRESENT:", "idDivBkt" in html, " bkt_init_widget_src:", "bkt_init_widget" in html)
finally:
    cita_auto.quit_driver(drv)
EOF_MARKER = True