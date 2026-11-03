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


def is_limited(html):
    """搜狗限流判定。

    正常搜索页约 30KB 以上；被限流时返回约 5KB 的空壳页（既无结果条目，
    也可能是 antispider 拦截页）。此时若照常把 0 条结果当作「无新增」，
    会把「被限流」误判成「上游没更新」，从而静默漏抓 —— 必须显式识别。
    """
    if len(html) > 12000:
        return False
    if "antispider" in html or "请输入验证码" in html or "用户您好" in html:
        return True
    return "<li id=\"sogou_vr_11002601_box_" not in html


def main():
    queries = [
        "华府卫视战报",
        "华府卫视昨日战报",
        "华府卫视 巅峰赛场",
        "华府卫视 黄金赛场",
        "鸡坛快迅 华府卫视",
        "读鸡坛快迅 品宁夏滩羊",
        "鸡坛快迅 巅峰赛场",
        # 下面这批是补充召回：搜狗对同一批词的返回量随限流波动，
        # 多几个入口能显著提高命中最新几期的概率（实测只靠前 7 个词
        # 会漏掉 11-03 那一期）。
        "华府战报",
        "华府 昨日战报",
        "巅峰赛场 BO7",
        "华府卫视 战报 团战",
        "鸡坛快迅 战报",
        "鸡坛快迅 星际",
        "星际 华府 战报",
        "华府 点播赛 战报",
    ]
    # 先访问一次首页拿到 cookie
    get("https://weixin.sogou.com/")
    time.sleep(1)

    all_items = {}
    # 与既有结果合并，而不是覆盖。
    # 搜狗的召回量随限流波动（同一批 query 有时只返回几页），
    # 覆盖式写盘会让上一轮已发现的文章凭空消失，进而漏抓。
    if os.path.exists(OUT):
        try:
            for old in json.load(open(OUT, encoding="utf-8")):
                all_items[old["title"][:40]] = old
            print("载入既有结果:", len(all_items))
        except Exception as e:
            print("! 既有结果读取失败，将重新采集：", e)
    limited = False
    for q in queries:
        for page in range(1, 11):
            url = "%s?type=2&query=%s&page=%d" % (BASE, urllib.parse.quote(q), page)
            html = get(url, referer="https://weixin.sogou.com/")
            if is_limited(html):
                # 已被限流：继续换词换页只会浪费时间，且加重封禁。
                print("! 搜狗限流（q=%s page=%d，返回 %d 字节空壳页），本轮采集提前结束"
                      % (q, page, len(html)))
                limited = True
                break
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
        if limited:
            break

    # 限流时**不写盘**：本轮一条都没采到，写下去只会用残缺数据覆盖
    # 上一轮更完整的清单（历史踩坑：search_results.json 一夜之间少了近千行）。
    if limited:
        print("LIMITED：本轮未采到任何新结果，保留既有清单不动")
        print("既有结果条数: %d" % len(all_items))
        sys.exit(2)

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
