# -*- coding: utf-8 -*-
"""用本机 Chrome + CDP 打开 wxredian，通过 Cloudflare Turnstile，取回 cookie 与作者页链接。"""
import json, subprocess, time, os, sys, urllib.request
import websocket

CHROME = r"C:\Users\yanwx\AppData\Local\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\tmp\cdpprof"
PORT = 9222
TARGET = sys.argv[1] if len(sys.argv) > 1 else "https://wxredian.com/art?id=0f69dbe758d57de5373fbf469ed1ac82"

os.makedirs(PROFILE, exist_ok=True)

proc = subprocess.Popen([
    CHROME,
    "--remote-debugging-port=%d" % PORT,
    "--remote-allow-origins=*",
    "--user-data-dir=" + PROFILE,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=Translate",
    "--window-size=1200,900",
    "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 等 Chrome 起来
ws_url = None
for _ in range(40):
    time.sleep(0.5)
    try:
        data = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=3))
        pages = [d for d in data if d.get("type") == "page"]
        if pages:
            ws_url = pages[0]["webSocketDebuggerUrl"]
            break
    except Exception:
        pass

if not ws_url:
    print("FAIL: cannot connect to chrome")
    proc.terminate()
    sys.exit(1)

print("ws:", ws_url)
ws = websocket.create_connection(ws_url, timeout=60)
mid = [0]


def cmd(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid[0]:
            return msg.get("result", msg)


cmd("Page.enable")
cmd("Network.enable")
cmd("Page.navigate", {"url": TARGET})
time.sleep(12)  # 等 Turnstile 自动完成 + 页面跳转

r = cmd("Runtime.evaluate", {
    "expression": "JSON.stringify({title:document.title,url:location.href,"
                  "author:(document.querySelector('a[href*=\"author\"]')||{}).href||'',"
                  "links:Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')).filter(h=>h&&h.indexOf('author')>=0).slice(0,5)})",
    "returnByValue": True})
print("PAGE:", r.get("result", {}).get("value"))

ck = cmd("Network.getAllCookies")
cookies = [c for c in ck.get("cookies", []) if "wxredian" in c.get("domain", "")]
print("COOKIES:", json.dumps(cookies, ensure_ascii=False))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cookies.json"), "w",
          encoding="utf-8") as f:
    json.dump(cookies, f, ensure_ascii=False, indent=1)

ws.close()
proc.terminate()
print("closed")
