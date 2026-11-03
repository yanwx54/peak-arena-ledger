# -*- coding: utf-8 -*-
"""搜狗微信 → 微信公众号原文 的补抓通路（wxredian 不可达时的备用数据源）。

背景：
    归档站 wxredian.com 在本机网络被阻断（IP 层 + SNI 层双重封锁），
    主链路 list_articles.py / fetch_all.py 全部拿不到数据。
    但搜狗微信搜索（weixin.sogou.com）本机可达，且其 /link 跳转链可以还原出
    mp.weixin.qq.com 的签名原文 URL —— 直连微信公众号，绕开 wxredian 的 Cloudflare。

产出：
    data/articles/<id>.txt        正文纯文本（与主链路同目录、同格式）
    data/sogou_articles.json      条目清单，字段与 articles_list.json 一致，
                                   额外带 source/mid/idx/biz 便于溯源

ID 规则：
    md5(biz + "|" + mid + "|" + idx)，32 位十六进制，与 wxredian 的 id 形态一致。
    同一篇文章无论经由哪个数据源抓到，id 稳定 → 正文不会重复落盘。

去重口径（与主链路一致，由 build_output.py 统一执行）：
    去重键 = (比赛日, 选手1, 比分, 选手2)
    比赛日 = 发布日 - 1 天
"""
import re
import os
import sys
import json
import time
import html as H
import hashlib
import datetime
import urllib.request
import urllib.parse
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")
OUT_JSON = os.path.join(DATA, "sogou_articles.json")
SEARCH_JSON = os.path.join(DATA, "search_results.json")

os.makedirs(ART, exist_ok=True)

# 标题归一化与 merge_sources 共用同一套规则，保证两边判重口径一致
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_sources import norm_title  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 搜狗会话：先访问首页拿 SNUID / SUID / ABTEST，否则 /link 会跳 /antispider/
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9")]


def get(url, referer=None, timeout=40):
    req = urllib.request.Request(url)
    if referer:
        req.add_header("Referer", referer)
    return opener.open(req, timeout=timeout).read().decode("utf-8", "ignore")


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|section|div|h\d|li|tr|td)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = H.unescape(s)
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


# ---------------- 搜狗跳转链还原 ----------------

def resolve_sogou(link):
    """搜狗 /link?url=... → mp.weixin.qq.com 签名原文 URL。

    跳转页是一个 JS 壳，真正的地址被拆成若干 `url += '...'` 片段，
    需要按出现顺序拼接；个别页面直接给 location.replace("...")。

    注意：必须先访问过搜索结果页（拿到 ABTEST / SNUID / SUID），
    否则这里会直接跳 /antispider/ 且页面里没有 url 片段。

    两种失败要分开：
      - None        → 限流/拦截，拿不到链接；
      - 抛异常      → 网络问题。
    """
    h = get("https://weixin.sogou.com" + link, referer="https://weixin.sogou.com/")
    parts = re.findall(r"url \+= '([^']*)'", h)
    url = "".join(parts) if parts else ""
    if not url:
        m = re.search(r"location\.replace\(\"([^\"]+)\"\)", h)
        if m:
            url = m.group(1)
    if not url:
        # 兜底：页面里任何 mp.weixin.qq.com 开头的串
        m = re.search(r"(https?://mp\.weixin\.qq\.com[^\s\"'<>]*)", h)
        if m:
            url = m.group(1)
    if not url:
        return None
    # JS 壳里还有 url.replace("@","")，这里同步处理
    url = url.replace("@", "")
    # 片段拼接偶尔会在主机名后多出一个 'om'（.com + om 拼接残留）
    url = url.replace("mp.weixin.qq.comom", "mp.weixin.qq.com")
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def looks_limited(page):
    """微信原文页是否被限流/拦截。"""
    if len(page) > 20000:
        return False
    return ("环境异常" in page or "参数错误" in page
            or "该内容已被发布者删除" in page or 'id="js_content"' not in page)


# ---------------- 原文抓取与解析 ----------------

def parse_article(page):
    """从微信原文 HTML 中抽出标题、发布时刻、正文、身份标识。"""
    mt = re.search(r"var msg_title = (.*?);\n", page)
    title = ""
    if mt:
        title = strip_tags(mt.group(1).replace(".html(false)", "").strip("'\""))
    if not title:
        mo = re.search(r'<meta property="og:title" content="([^"]*)"', page)
        if mo:
            title = H.unescape(mo.group(1)).strip()

    ct = re.search(r'var ct = "(\d+)"', page)
    ts = int(ct.group(1)) if ct else 0

    un = re.search(r'var user_name = "([^"]*)"', page)
    user = un.group(1) if un else ""
    biz = re.search(r'var biz = "([^"]*)"', page)
    biz = biz.group(1) if biz else ""
    mid = re.search(r'var mid = "?\d+', page)
    mid = re.search(r'var mid = "?(\d+)', page)
    mid = mid.group(1) if mid else ""
    idx = re.search(r'var idx = "?(\d+)', page)
    idx = idx.group(1) if idx else ""

    # 正文：js_content 容器 → rich_media_area_extra 之前
    i = page.find('id="js_content"')
    if i < 0:
        return None
    body = page[i:]
    stop = body.find('rich_media_area_extra')
    if stop > 0:
        body = body[:stop]
    else:
        body = body[:1500000]
    text = strip_tags(body)
    if len(text) < 50:
        return None
    return {"title": title, "ts": ts, "text": text,
            "user": user, "biz": biz, "mid": mid, "idx": idx}


def make_id(biz, mid, idx):
    raw = "%s|%s|%s" % (biz, mid, idx)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ---------------- 主流程 ----------------

def load_search():
    """读取搜狗搜索结果；没有就地跑一次 harvest。"""
    rows = []
    if os.path.exists(SEARCH_JSON):
        try:
            rows = json.load(open(SEARCH_JSON, encoding="utf-8"))
        except Exception:
            rows = []
    if not rows:
        print("! search_results.json 不可用，执行 harvest.py")
        import subprocess
        subprocess.run([sys.executable, os.path.join(HERE, "harvest.py")], cwd=HERE)
        rows = json.load(open(SEARCH_JSON, encoding="utf-8"))
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="只抓发布日期 >= YYYY-MM-DD 的文章")
    ap.add_argument("--limit", type=int, default=0, help="最多抓多少篇（0=不限）")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不抓正文")
    args = ap.parse_args()

    rows = load_search()
    jt = [r for r in rows if r.get("account") == "鸡坛快迅"]
    jt.sort(key=lambda r: r.get("ts", 0))

    if args.since:
        cut = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
        jt = [r for r in jt if r.get("ts", 0) >= cut]

    # 已抓过的（按 md5(biz|mid|idx) 去重靠正文文件本身判断，这里先按标题粗筛）
    print("待处理候选：%d 篇（%s 起）" % (len(jt), args.since or "不限"))
    for r in jt:
        dt = datetime.datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M")
        print("  %s | %s" % (dt, r["title"][:56]))

    if args.dry_run:
        return 0

    # 建立搜狗会话：必须访问搜索结果页，才能拿到 ABTEST / SNUID / SUID。
    # 只访问首页的话，/link 会跳 /antispider/，还原不出 mp.weixin.qq.com 地址。
    try:
        get("https://weixin.sogou.com/")
        time.sleep(0.6)
        q = urllib.parse.quote("华府卫视战报")
        get("https://weixin.sogou.com/weixin?type=2&query=%s" % q,
            referer="https://weixin.sogou.com/")
    except Exception as e:
        print("! 无法访问搜狗：%r" % e)
        return 2
    names = sorted(c.name for c in cj)
    print("搜狗会话 cookie：%s" % (", ".join(names) or "无"))
    if "SNUID" not in names:
        print("! 未拿到 SNUID，跳转链会失效")
        return 2
    time.sleep(1.0)

    existing = {}
    if os.path.exists(OUT_JSON):
        try:
            existing = {x["id"]: x for x in json.load(open(OUT_JSON, encoding="utf-8"))}
        except Exception:
            existing = {}

    # 已抓过的（按 发布日+标题 粗筛）—— 命中就跳过，避免重复下载正文。
    # 标题在两源间可能有出入（如「迷你6杀AK」vs「迷你7杀AK」），
    # 所以同一天只放行一篇：本号每天至多发一篇战报。
    done_days = {}
    for x in existing.values():
        done_days.setdefault((x.get("date") or "")[:10], set()).add(norm_title(x.get("title")))

    ok = 0
    n = 0
    for r in jt:
        n += 1
        if args.limit and ok >= args.limit:
            break
        ts = r.get("ts", 0)
        pub = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        day = pub[:10]
        # 同一天已处理过 → 跳过，不再重复下载正文。
        # 两种情况都归到这里：
        #   a) 就是同一篇（标题归一化命中）—— 正文已在本地；
        #   b) 同一天的另一篇 —— 本号每天至多发一篇战报，已覆盖。
        if day in done_days:
            print("[%d] 跳过 %s：该日已处理（%s）" % (n, day, r["title"][:36]))
            continue
        try:
            wxurl = resolve_sogou(r["link"])
            if not wxurl:
                print("[%d] resolve 失败（搜狗限流或签名过期）：%s" % (n, r["title"][:40]))
                continue
            time.sleep(1.0)
            page = get(wxurl, referer="https://mp.weixin.qq.com/", timeout=50)
            if looks_limited(page):
                print("[%d] 微信原文页被限流/拦截：%s" % (n, r["title"][:40]))
                continue
            art = parse_article(page)
            if not art:
                print("[%d] 正文提取失败：%s" % (n, r["title"][:40]))
                continue
            if art["user"] and art["user"] != "gh_72517d36a4d7":
                print("[%d] 跳过：公众号不匹配 (%s)" % (n, art["user"]))
                continue

            aid = make_id(art["biz"], art["mid"], art["idx"])
            fp = os.path.join(ART, aid + ".txt")
            if not (os.path.exists(fp) and os.path.getsize(fp) > 200):
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(art["text"])

            existing[aid] = {
                "id": aid,
                "title": art["title"] or r["title"],
                "date": pub,
                "cycle": pub[:4] + pub[5:7],
                "source": "sogou",
                "biz": art["biz"],
                "mid": art["mid"],
                "idx": art["idx"],
                "chars": len(art["text"]),
                "has_jd": "巅峰赛场" in art["text"],
                "sogou_title": r["title"],
            }
            ok += 1
            done_days.setdefault(day, set()).add(norm_title(art["title"] or r["title"]))
            print("[%d] OK %s | JD=%s | %d字 | %s"
                  % (n, pub, "是" if "巅峰赛场" in art["text"] else "否",
                     len(art["text"]), (art["title"] or r["title"])[:44]))
        except Exception as e:
            print("[%d] ERR %r | %s" % (n, e, r["title"][:36]))
        time.sleep(1.2)

    data = sorted(existing.values(), key=lambda x: x["date"])
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("完成：本次新增 %d 篇，累计 %d 篇 → %s" % (ok, len(data), OUT_JSON))
    return 0


if __name__ == "__main__":
    sys.exit(main())
