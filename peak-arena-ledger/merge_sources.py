# -*- coding: utf-8 -*-
"""多源文章清单合并：wxredian（主源） + 搜狗微信（备源）。

背景：
    归档站 wxredian.com 被网络封锁时，list_articles.py 会写出一份空/残缺的
    articles_list.json，直接覆盖好数据。于是引入搜狗微信作为备源：
    sogou_fetch.py 抓到的文章写在 data/sogou_articles.json，本脚本负责
    把它并进 articles_list.json。

合并键：标题归一化（去掉所有标点与空白，全角/半角统一）。
    两个来源的同一篇文章，标题里只有全角/半角标点之差
    （wxredian 用「，」，搜狗用「,」），归一化后即可对齐。
    命中时以主源（wxredian）条目为准 —— 主源恢复后自动收敛，不会双份计数。

写入策略：先读现有 articles_list.json，再合并写回，**不删除任何已有条目**。
    这样即使主源这轮完全不可用，旧数据也一份不少。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
LIST = os.path.join(DATA, "articles_list.json")
SOGOU = os.path.join(DATA, "sogou_articles.json")

# 全角标点 → 半角，再去掉所有标点/空白，只留文字与字母数字
_PUNCT = re.compile(r"[\s\u3000!-/:-@\[-`{-~！-～、-〿＀-￯]+")


def norm_title(t):
    if not t:
        return ""
    t = t.replace("：", ":").replace("，", ",").replace("；", ";")
    t = t.replace("！", "!").replace("？", "?")
    t = re.sub(r"^鸡坛快迅\s*[:：]\s*", "", t.strip())
    return _PUNCT.sub("", t).lower()


def load(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("! 读取 %s 失败：%r" % (os.path.basename(path), e))
        return default


def main():
    base = load(LIST, [])
    sg = load(SOGOU, [])

    by_norm = {}
    by_day = {}
    for r in base:
        k = norm_title(r.get("title"))
        if k and k not in by_norm:
            by_norm[k] = r
        day = (r.get("date") or "")[:10]
        if day:
            by_day.setdefault(day, set()).add(k)

    added = 0
    dup = 0
    for r in sg:
        k = norm_title(r.get("title"))
        if not k:
            continue
        day = (r.get("date") or "")[:10]
        # 双重判重：标题归一化命中，或「同一天已有该号文章」。
        # 后者覆盖标题在两源间有出入的情况（实测 2026-10-27 一篇：
        # 搜狗写「迷你6杀AK」，主源写「迷你7杀AK」，归一化对不上）。
        # 同一公众号同一天只发一篇战报，用日期兜底不会误杀不同文章。
        if k in by_norm or (day and k in by_day.get(day, ())):
            dup += 1
            continue
        entry = {"id": r["id"], "title": r["title"], "date": r["date"],
                 "cycle": r.get("cycle") or r["date"][:4] + r["date"][5:7]}
        base.append(entry)
        by_norm[k] = entry
        by_day.setdefault(day, set()).add(k)
        added += 1

    # 日期排序（缺失日期的排最后）
    base.sort(key=lambda r: (r.get("date") or "9999", r.get("title") or ""))

    with open(LIST, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=1)

    print("主源条目: %d | 备源条目: %d" % (len(base) - added, len(sg)))
    print("新增: %d | 与主源重复（已跳过）: %d | 合并后总计: %d"
          % (added, dup, len(base)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
