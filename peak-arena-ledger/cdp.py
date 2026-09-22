# -*- coding: utf-8 -*-
"""用本机 Chrome + CDP 打开 wxredian，通过 Cloudflare Turnstile，取回 cookie。

⚠️ 关键：wxredian 会对请求下发 Turnstile「验证访问」页，**光有 cookie 不够**，
必须等页面真正通过验证（标题不再是「验证访问」、且能拿到文章链接）之后再取 cookie，
否则取到的是一份无效 cookie，后续批量抓取会全部拿到验证页。

因此本脚本：
1. 打开作者页（正是抓取时要用的页面）；
2. 轮询等待验证通过，最长 CDP_WAIT_MAX 秒（默认 150）；
3. 取 cookie 落盘；
4. 用该 cookie 实际请求一次作者页做校验，不通则退出码 1。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CHROME = r"C:\Users\yanwx\AppData\Local\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\tmp\cdpprof"
PORT = 9222
AUTHOR_ID = "gh_72517d36a4d7"
AUTHOR_URL = "https://wxredian.com/author?id=%s" % AUTHOR_ID
TARGET = sys.argv[1] if len(sys.argv) > 1 else AUTHOR_URL
WAIT_MAX = int(os.environ.get("CDP_WAIT_MAX", "150"))

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(HERE, "data", "cookies.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

os.makedirs(PROFILE, exist_ok=True)
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)

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

ws = websocket.create_connection(ws_url, timeout=60)
mid = [0]


def cmd(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid[0]:
            return msg.get("result", msg)


def evaluate(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("value")


cmd("Page.enable")
cmd("Network.enable")
cmd("Page.navigate", {"url": TARGET})

# ---------- 轮询等待 Turnstile 验证通过 ----------
PROBE = ("JSON.stringify({title:document.title,"
         "links:document.querySelectorAll('a[href*=\"/art?id=\"]').length})")

verified = False
t0 = time.time()
last = ""
while time.time() - t0 < WAIT_MAX:
    time.sleep(2)
    raw = evaluate(PROBE)
    if not raw:
        continue
    info = json.loads(raw)
    title, links = info.get("title", ""), info.get("links", 0)
    if (title, links) != last:
        print("  [%3ds] title=%r links=%d" % (int(time.time() - t0), title, links))
        last = (title, links)
    if "验证" not in title and links > 0:
        verified = True
        break

print("PAGE:", evaluate(PROBE))
print("验证耗时: %ds" % int(time.time() - t0))

if not verified:
    print("FAIL: Turnstile 未在 %ds 内通过（页面仍为验证页）" % WAIT_MAX)
    ws.close()
    proc.terminate()
    sys.exit(1)

# ---------- 取 cookie ----------
ck = cmd("Network.getAllCookies")
cookies = [c for c in ck.get("cookies", []) if "wxredian" in c.get("domain", "")]
print("COOKIES:", json.dumps([c["name"] for c in cookies], ensure_ascii=False))

with open(COOKIE_FILE, "w", encoding="utf-8") as f:
    json.dump(cookies, f, ensure_ascii=False, indent=1)

ws.close()
proc.terminate()

# ---------- 用该 cookie 实测一次，确认真的可用 ----------
COOKIE = "; ".join("%s=%s" % (c["name"], c["value"]) for c in cookies)
req = urllib.request.Request(TARGET)
req.add_header("User-Agent", UA)
req.add_header("Cookie", COOKIE)
req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
try:
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
except Exception as e:
    print("FAIL: 校验请求异常 %s: %s" % (type(e).__name__, e))
    sys.exit(1)

n_art = h.count("/art?id=")
if n_art == 0 or "验证访问" in h:
    print("FAIL: cookie 校验未通过（文章链接数 %d，页面含验证页）" % n_art)
    sys.exit(1)

print("OK: cookie 可用（作者页文章链接 %d 个）" % n_art)
print("closed")
