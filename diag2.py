#!/usr/bin/env python3
"""In-vivo capture: what the REAL widget sends after boot, and what it gets back."""
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
            print("CF challenge FAILED", flush=True)
            return 1
        for attempt in range(4):
            time.sleep(2)
            diag = {}
            try:
                diag = json.loads(drv.execute_script(
                    "return JSON.stringify({bkt:(typeof bkt_init_widget!=='undefined'),"
                    "jq:(typeof window.jQuery!=='undefined')})"))
            except Exception as e:
                print(f"boot check err: {e}", flush=True)
            print(f"boot: {json.dumps(diag)} (attempt {attempt + 1})", flush=True)
            if diag.get("bkt") and diag.get("jq"):
                break
            if attempt < 3:
                drv.get(conf["widget_url"])
                time.sleep(8)

        info = drv.execute_script(
            "var BIW = (typeof bkt_init_widget!=='undefined') ? bkt_init_widget : null;"
            "var s = {};"
            "if(BIW){ try{s.biw=JSON.stringify(BIW).substring(0,4000);}catch(e){s.biw='unserializable';} }"
            "try{s.services=JSON.stringify(BIW.services || BIW.Services || null);}catch(e){}"
            "try{s.agendas=JSON.stringify(BIW.agendas || BIW.Agendas || null);}catch(e){}"
            "try{s.dates=JSON.stringify(BIW.dates || BIW.Dates || null);}catch(e){}"
            "try{s.api=JSON.stringify(BIW.api || BIW.apiBase || BIW.API || null);}catch(e){}"
            "try{s.jquery=JSON.stringify($.fn.jquery);}catch(e){s.jquery=null;}"
            "var res = performance.getEntriesByType('resource')"
            "  .map(function(e){return e.name}).filter(function(u){return u.indexOf('onlinebookings')>=0});"
            "s.res=JSON.stringify(res);"
            "return JSON.stringify(s);"
        )
        d = json.loads(info)
        print("== bkt_init_widget ==", flush=True)
        print((d.get("biw") or "-")[:4000], flush=True)
        print("== services ==", (d.get("services") or "-")[:800], flush=True)
        print("== agendas ==", (d.get("agendas") or "-")[:800], flush=True)
        print("== dates ==", (d.get("dates") or "-")[:800], flush=True)
        print("== api fields ==", (d.get("api") or "-")[:400], flush=True)
        print("== jquery ==", d.get("jquery"), flush=True)
        print("== onlinebookings resources loaded by boot ==", flush=True)
        res = json.loads(d.get("res") or "[]")
        for u in res:
            print("   ", u[:300], flush=True)

        print("== manual XHR variants (all with config api_base) ==", flush=True)
        script = (
            "var variants=arguments[0],done=arguments[1],out=[],i=0;"
            "function next(){"
            "  if(i>=variants.length){done(JSON.stringify(out));return;}"
            "  var v=variants[i++],req=new XMLHttpRequest();"
            "  req.open(v.m,v.u,true);req.withCredentials=true;"
            "  if(v.m==='POST'){req.setRequestHeader('Content-Type','application/x-www-form-urlencoded; charset=UTF-8');}"
            "  req.onload=function(){out.push({m:v.m,u:v.u,status:req.status,ctype:req.getResponseHeader('Content-Type')||'',"
            "    len:req.responseText.length,head:req.responseText.substring(0,300),error:null});next();};"
            "  req.onerror=function(){out.push({m:v.m,u:v.u,error:'xhr-error'});next();};"
            "  req.ontimeout=function(){out.push({m:v.m,u:v.u,error:'timeout'});next();};"
            "  req.timeout=25000;req.send(v.b||null);"
            "}"
            "next();"
        )
        base = conf["api_base"]
        cb = "jQuery21105666899906434029_1787235399356"
        wp = ("type=default&publickey=" + conf["office_hash"] + "&lang=es&version=4&src="
              + conf["widget_url"])
        basep = wp + "&services=&agendas=&dates=&srvsrc=https%3A%2F%2Fwww.citaconsular.es"
        svc = "services%5B%5D=bkt739959"
        now = int(time.time() * 1000)
        variants = [
            {"m": "GET", "u": f"{base}main/?callback={cb}&{wp}&_={now}"},
            {"m": "GET", "u": f"{base}main/?callback={cb}&{basep}&_={now}"},
            {"m": "GET", "u": f"{base}getwidgetconfigurations/?callback={cb}&{wp}&_={now}"},
            {"m": "GET", "u": f"{base}getwidgetconfigurations/?callback={cb}&{basep}&_={now}"},
            {"m": "GET", "u": f"{base}getservices/?callback={cb}&{wp}&{svc}&_={now}"},
            {"m": "GET", "u": f"{base}datetime/?callback={cb}&{wp}&{svc}"
                               f"&start=2026-08-01&end=2026-08-31&selectedPeople=1&_={now}"},
            {"m": "GET", "u": f"{base}main/?{wp}&_={now}"},
            {"m": "POST", "u": f"{base}main/", "b": f"callback={cb}&{wp}"},
            {"m": "POST", "u": f"{base}getwidgetconfigurations/", "b": f"callback={cb}&{basep}"},
        ]
        out = json.loads(drv.execute_async_script(script, variants))
        for o in out:
            print(json.dumps(o)[:350], flush=True)

        try:
            drv.save_screenshot(os.path.join(ca.STATE_DIR, "diag2.png"))
        except Exception:
            pass
        return 0
    finally:
        ca.quit_driver(drv)


if __name__ == "__main__":
    sys.exit(main())