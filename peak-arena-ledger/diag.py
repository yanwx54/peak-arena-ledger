# -*- coding: utf-8 -*-
"""自检：检查「巅峰赛场」战绩是否被漏掉。

两道检查：
  A. 已匹配到战报段、段内有「巅峰赛场」却没解析出战绩；
  B. 全文含「巅峰赛场」却没解析出任何战绩（能发现整段被跳过的情况，
     例如 2026-03-28 战报段漏写【】表头）。

检查 B 是 2026-09-23 补的：此前只做 A，而当时真正的漏抓是「整个战报段没被匹配到」，
A 自然报 0，自检形同虚设。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")

sys.path.insert(0, HERE)
from extract_jd import get_sections, parse_section, parse_unanchored

rows = json.load(open(os.path.join(DATA, "articles_list.json"), encoding="utf-8"))

n_sec = 0
miss_in_sec = []   # A：段内有条目却零解析
miss_no_sec = []   # B：全文有「巅峰赛场」却零解析

for r in sorted(rows, key=lambda x: x["date"]):
    fp = os.path.join(ART, r["id"] + ".txt")
    if not os.path.exists(fp):
        continue
    text = open(fp, encoding="utf-8").read()
    secs = get_sections(text)
    got = []
    for s in secs:
        got += parse_section(s)
    if not got:
        got = parse_unanchored(text)

    if secs:
        n_sec += 1
        if "巅峰赛场" in "\n".join(secs) and not got:
            miss_in_sec.append((r, "\n".join(secs)))

    if "巅峰赛场" in text and not got:
        miss_no_sec.append((r, text))

print("articles with 战报 section:", n_sec)
print("A. 段内有「巅峰赛场」但零解析:", len(miss_in_sec))
print("B. 全文有「巅峰赛场」但零解析:", len(miss_no_sec))

for tag, items in (("A", miss_in_sec), ("B", miss_no_sec)):
    for r, body in items[:15]:
        print("=" * 70)
        print("[%s] %s  %s" % (tag, r["date"], r["title"][:50]))
        print(body[:700])

sys.exit(1 if (miss_in_sec or miss_no_sec) else 0)
