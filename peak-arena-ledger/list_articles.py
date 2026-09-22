# -*- coding: utf-8 -*-
"""从 wxredian 作者页按月+分页拉取「鸡坛快迅」全部文章列表。"""
import re, json, time, os, html as H
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
COOKIE = "; ".join("%s=%s" % (c["name"], c["value"])
                   for c in json.load(open(os.path.join(DATA, "cookies.json"), encoding="utf-8")))
AUTHOR = "gh_72517d36a4d7"


def get(url):
    last = None
    for _ in range(5):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            req.add_header("Cookie", COOKIE)
            req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(3)
    raise last


def strip(s):
    return H.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_list(h):
    out = []
    for m in re.finditer(
            r'<a[^>]*href="/art\?id=([a-f0-9]+)"[^>]*class="[^"]*pb-keywords-highlight[^"]*"[^>]*>(.*?)</a>',
            h, re.S):
        aid, title = m.group(1), strip(m.group(2))
        seg = h[m.end():m.end() + 1200]
        dm = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", seg)
        out.append({"id": aid, "title": title, "date": dm.group(1) if dm else ""})
    return out


def main():
    allrows = {}
    cycles = ["202512"] + ["2026%02d" % m for m in range(1, 10)]
    for c in cycles:
        page = 1
        got = 0
        while page <= 6:
            url = "https://wxredian.com/author?id=%s&cycle=%s" % (AUTHOR, c)
            if page > 1:
                url += "&page=%d" % page
            try:
                h = get(url)
            except Exception as e:
                print(c, page, "ERR", e)
                break
            rows = parse_list(h)
            if not rows:
                break
            tot = re.search(r"共找到 <span[^>]*>(\d+)</span> 条记录", h)
            for r in rows:
                r["cycle"] = c
                allrows[r["id"]] = r
            got += len(rows)
            print("cycle=%s page=%d parsed=%d (total %s)" % (c, page, len(rows), tot.group(1) if tot else "?"))
            if len(rows) < 30:
                break
            page += 1
            time.sleep(0.6)
        time.sleep(0.6)

    data = sorted(allrows.values(), key=lambda x: x["date"])
    with open(os.path.join(DATA, "articles_list.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("TOTAL unique articles:", len(data))
    nod = [d for d in data if not d["date"]]
    print("missing date:", len(nod))
    for d in data[:2] + data[-2:]:
        print("  ", d["date"], d["title"][:45])


if __name__ == "__main__":
    main()
