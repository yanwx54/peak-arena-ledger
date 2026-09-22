# -*- coding: utf-8 -*-
"""抓取 wxredian 上「鸡坛快迅」每篇文章正文，保存为 txt。"""
import re, json, time, os, html as H, sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")
os.makedirs(ART, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
COOKIE = "; ".join("%s=%s" % (c["name"], c["value"])
                   for c in json.load(open(os.path.join(DATA, "cookies.json"), encoding="utf-8")))


def get(url):
    last = None
    for _ in range(4):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            req.add_header("Cookie", COOKIE)
            req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
            return urllib.request.urlopen(req, timeout=35).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def strip(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|section|div|h\d|li|tr|td)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = H.unescape(s).replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def main():
    rows = json.load(open(os.path.join(DATA, "articles_list.json"), encoding="utf-8"))
    print("articles:", len(rows))
    ok = 0
    for n, r in enumerate(rows, 1):
        fp = os.path.join(ART, r["id"] + ".txt")
        if os.path.exists(fp) and os.path.getsize(fp) > 200:
            ok += 1
            continue
        try:
            h = get("https://wxredian.com/art?id=" + r["id"])
            i = h.find('id="art-content"')
            if i < 0:
                print(n, "no content", r["id"])
                continue
            body = h[i:]
            body = body[:body.find('id="art-content"') + 1] if False else body
            stop = body.find('<div class="ub-content-box', 30)
            if stop > 0:
                body = body[:stop]
            txt = strip(body)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(txt)
            ok += 1
            if n % 20 == 0:
                print("progress", n, "/", len(rows))
        except Exception as e:
            print(n, "ERR", repr(e)[:70])
        time.sleep(0.35)
    print("saved:", ok, "/", len(rows))


if __name__ == "__main__":
    main()
