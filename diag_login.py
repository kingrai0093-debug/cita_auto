#!/usr/bin/env python3
"""Diagnose widget DOM WITHOUT reloads: dump iframes + login form structure."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cita_auto as ca

DUMP = (
    "var out={href:location.href,title:document.title,frames:[],html:''};"
    "var ifs=document.querySelectorAll('iframe');"
    "for(var i=0;i<ifs.length;i++){var f=ifs[i];"
    "  var d=f.contentDocument;var fd={id:f.id||'',src:(f.src||'').substring(0,120),forms:[],inputs:[],body:''};"
    "  if(d){fd.body=d.body?d.body.innerText.substring(0,600):'';"
    "    var fs=d.querySelectorAll('form');"
    "    for(var j=0;j<fs.length;j++){var fm=fs[j];var ins=[];"
    "      var els=fm.querySelectorAll('input,select,textarea');"
    "      for(var k=0;k<els.length;k++){var e=els[k];"
    "        ins.push({tag:e.tagName,id:e.id||'',name:e.name||'',type:e.type||'',ph:e.placeholder||''});}"
    "      fd.forms.push({id:fm.id||'',name:fm.name||'',action:(fm.action||'').substring(0,100),inputs:ins});}"
    "    var bs=d.querySelectorAll('button,input[type=submit],input[type=button]');"
    "    fd.btns=[];"
    "    for(var b=0;b<bs.length;b++){var x=bs[b];"
    "      fd.btns.push({id:x.id||'',value:x.value||'',text:(x.textContent||'').trim().substring(0,30)});}"
    "  }"
    "  out.frames.push(fd);}"
    "var ds=document.querySelectorAll('input,select,textarea');out.inputs=[];"
    "for(var m=0;m<ds.length;m++){var t=ds[m];"
    "  out.inputs.push({tag:t.tagName,id:t.id||'',name:t.name||'',type:t.type||'',ph:t.placeholder||''});}"
    "out.btns=[];"
    "var bs2=document.querySelectorAll('button,input[type=submit],input[type=button]');"
    "for(var n=0;n<bs2.length;n++){var y=bs2[n];"
    "  out.btns.push({id:y.id||'',value:y.value||'',text:(y.textContent||'').trim().substring(0,30)});}"
    "out.body=document.body?document.body.innerText.substring(0,800):'';"
    "out.html=document.documentElement?document.documentElement.outerHTML.substring(0,1500):'';"
    "return JSON.stringify(out);"
)


def dump(drv, label):
    try:
        d = json.loads(drv.execute_script(DUMP))
    except Exception as e:
        print(f"[{label}] dump err: {e}", flush=True)
        return
    print(f"===== {label} =====", flush=True)
    print(f"href={d['href']} title={d['title']}", flush=True)
    print(f"top body: {d['body'][:300]!r}", flush=True)
    print(f"-- top inputs ({len(d.get('inputs', []))}) --", flush=True)
    for i in d.get("inputs", []):
        print(f"   {i['tag']} id={i['id']!r} name={i['name']!r} type={i['type']!r} ph={i['ph']!r}", flush=True)
    print(f"-- top buttons ({len(d.get('btns', []))}) --", flush=True)
    for b in d.get("btns", [])[:15]:
        print(f"   {b['id']!r} value={b['value']!r} text={b['text']!r}", flush=True)
    for f in d.get("frames", []):
        print(f"-- iframe id={f['id']!r} src={f['src']!r} --", flush=True)
        print(f"   iframe body: {f['body'][:300]!r}", flush=True)
        for fm in f.get("forms", []):
            print(f"   FORM id={fm['id']!r} name={fm['name']!r} action={fm['action']!r}", flush=True)
            for i in fm.get("inputs", []):
                print(f"     {i['tag']} id={i['id']!r} name={i['name']!r} type={i['type']!r} ph={i['ph']!r}", flush=True)
        for b in f.get("btns", [])[:15]:
            print(f"   BTN {b['id']!r} value={b['value']!r} text={b['text']!r}", flush=True)


def main():
    conf = ca.load_conf()
    drv = ca.browser_new(conf)
    try:
        if not ca.solve_challenge(drv, conf):
            print("CF challenge FAILED", flush=True)
            return 1
        time.sleep(2)
        ca.capture_session(drv, conf)
        dump(drv, "after gate (default view)")

        for step in ("signinaccount", "services", "datetime", "agenda"):
            print(f"\n>> navigating to #{step} via location.hash (no reload)", flush=True)
            try:
                drv.execute_script("location.hash='" + step + "'")
            except Exception as e:
                print(f"   hash nav err: {e}", flush=True)
            time.sleep(7)
            dump(drv, f"#{step} view")

        try:
            drv.save_screenshot(os.path.join(ca.STATE_DIR, "login_diag.png"))
        except Exception:
            pass
        return 0
    finally:
        ca.quit_driver(drv)


if __name__ == "__main__":
    sys.exit(main())