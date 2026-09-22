# -*- coding: utf-8 -*-
"""通过搜狗微信搜索枚举「鸡坛快迅」公众号文章。"""
import re, json, time, os, sys, urllib.parse
import urllib.request, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://weixin.sogou.com/weixin"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9")]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "search_results.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def get(url, referer=None):
    req = urllib.request.Request(url)
    if referer:
        req.add_header("Referer", referer)
    for attempt in range(3):
        try:
            return opener.open(req, timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:
            print("  ! err", e, file=sys.stderr)
            time.sleep(3)
    return ""


def parse(html):
    items = []
    for block in re.split(r"<li id=\"sogou_vr_11002601_box_", html)[1:]:
        block = block[:block.find("</li>")] if "</li>" in block else block
        m = re.search(r'<h3>\s*<a[^>]*href="(/link\?url=[^"]*)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        link = m.group(1).replace("&amp;", "&")
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        sm = re.search(r'<p class="txt-info"[^>]*>(.*?)</p>', block, re.S)
        snippet = ""
        if sm:
            snippet = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
        am = re.search(r'<span class="all-time-y2">(.*?)</span>', block, re.S)
        account = am.group(1).strip() if am else ""
        dm = re.search(r"timeConvert\('(\d+)'\)", block)
        ts = int(dm.group(1)) if dm else 0
        items.append({"title": title, "link": link, "snippet": snippet,
                      "account": account, "ts": ts})
    return items


def main():
    queries = [
        "华府卫视战报",
        "华府卫视昨日战报",
        "华府卫视 巅峰赛场",
        "华府卫视 黄金赛场",
        "鸡坛快迅 华府卫视",
        "读鸡坛快迅 品宁夏滩羊",
        "鸡坛快迅 巅峰赛场",
    ]
    # 先访问一次首页拿到 cookie
    get("https://weixin.sogou.com/")
    time.sleep(1)

    all_items = {}
    for q in queries:
        for page in range(1, 11):
            url = "%s?type=2&query=%s&page=%d" % (BASE, urllib.parse.quote(q), page)
            html = get(url, referer="https://weixin.sogou.com/")
            items = parse(html)
            print("q=%s page=%d -> %d" % (q, page, len(items)))
            if not items:
                break
            for it in items:
                key = it["title"][:40]
                if key not in all_items:
                    it["query"] = q
                    all_items[key] = it
            time.sleep(1.5)

    data = sorted(all_items.values(), key=lambda x: -x["ts"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("TOTAL unique:", len(data), "->", OUT)
    jt = [d for d in data if d["account"] == "鸡坛快迅"]
    print("鸡坛快迅:", len(jt))
    if jt:
        import datetime
        ds = [datetime.datetime.fromtimestamp(d["ts"]).strftime("%Y-%m-%d") for d in jt]
        print("date range:", min(ds), "~", max(ds))


if __name__ == "__main__":
    main()
