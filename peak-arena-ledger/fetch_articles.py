# -*- coding: utf-8 -*-
"""跟随搜狗跳转链接 -> 抓取微信原文 -> 提取正文文本。"""
import re, json, time, os, sys, html
import urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")
os.makedirs(ART, exist_ok=True)

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9")]


def get(url, referer=None, timeout=30):
    req = urllib.request.Request(url)
    if referer:
        req.add_header("Referer", referer)
    return opener.open(req, timeout=timeout).read().decode("utf-8", "ignore")


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|section|div|h\d|li|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def resolve_sogou(link):
    """搜狗 /link -> mp.weixin.qq.com 真实链接"""
    h = get("https://weixin.sogou.com" + link, referer="https://weixin.sogou.com/")
    parts = re.findall(r"url \+= '([^']*)'", h)
    if parts:
        return "".join(parts)
    # 有些页面直接给出 location.replace("...")
    m = re.search(r"location\.replace\(\"([^\"]+)\"\)", h)
    if m:
        return m.group(1)
    return None


def fetch_article(url):
    h = get(url, referer="https://mp.weixin.qq.com/", timeout=40)
    mt = re.search(r'var msg_title = (.*?);\n', h)
    title = ""
    if mt:
        title = strip_tags(mt.group(1).replace(".html(false)", "").replace("'", ""))
    ct = re.search(r'var ct = "(\d+)"', h)
    ts = int(ct.group(1)) if ct else 0
    i = h.find('id="js_content"')
    if i < 0:
        return None
    seg = h[i:]
    end = seg.find('</div>', seg.find('rich_media_content'))
    body = h[i:i + 400000]
    # 截取到 rich_media_area_extra 之前
    k = body.find('id="js_content"')
    body = body[k:]
    stop = body.find('rich_media_area_extra')
    if stop > 0:
        body = body[:stop]
    text = strip_tags(body)
    return {"title": title, "ts": ts, "text": text}


def main():
    with open(os.path.join(DATA, "search_results.json"), encoding="utf-8") as f:
        rows = json.load(f)
    rows = [r for r in rows if r["account"] == "鸡坛快迅"]
    rows.sort(key=lambda r: r["ts"])
    print("to fetch:", len(rows))

    index_path = os.path.join(DATA, "articles_index.json")
    index = {}
    if os.path.exists(index_path):
        index = json.load(open(index_path, encoding="utf-8"))

    get("https://weixin.sogou.com/")
    time.sleep(1)

    for n, r in enumerate(rows, 1):
        key = str(r["ts"])
        if key in index and index[key].get("ok"):
            continue
        try:
            wxurl = resolve_sogou(r["link"])
            if not wxurl:
                print(n, "resolve fail", r["title"][:30])
                index[key] = {"ok": False, "title": r["title"], "ts": r["ts"], "err": "resolve"}
                continue
            time.sleep(1.0)
            a = fetch_article(wxurl)
            if not a or len(a["text"]) < 50:
                print(n, "fetch fail", r["title"][:30])
                index[key] = {"ok": False, "title": r["title"], "ts": r["ts"], "err": "fetch"}
                continue
            fn = os.path.join(ART, "%d.txt" % a["ts"] if a["ts"] else key + ".txt")
            with open(fn, "w", encoding="utf-8") as f:
                f.write(a["text"])
            index[key] = {"ok": True, "title": a["title"] or r["title"], "ts": a["ts"] or r["ts"],
                          "file": os.path.basename(fn), "chars": len(a["text"]),
                          "has_jd": "巅峰赛场" in a["text"]}
            print(n, "OK", index[key]["title"][:40], index[key]["chars"])
        except Exception as e:
            print(n, "ERR", repr(e)[:80])
            index[key] = {"ok": False, "title": r["title"], "ts": r["ts"], "err": repr(e)[:60]}
        finally:
            if n % 5 == 0:
                json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(0.8)

    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in index.values() if v.get("ok"))
    print("done. ok=%d / %d" % (ok, len(index)))


if __name__ == "__main__":
    main()
