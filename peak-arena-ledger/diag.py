# -*- coding: utf-8 -*-
"""诊断：检查【华府卫视战报】段落中「巅峰赛场」是否被漏掉。"""
import re, json, os, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")
rows = json.load(open(os.path.join(DATA, "articles_list.json"), encoding="utf-8"))
SEC = re.compile(r"【\s*华府卫视[^】]{0,10}战报\s*】")
ANY = re.compile(r"【[^】]{0,30}】")

import sys
sys.path.insert(0, HERE)
from extract_jd import get_sections, parse_section

n_sec = 0
miss = []
for r in sorted(rows, key=lambda x: x["date"]):
    fp = os.path.join(ART, r["id"] + ".txt")
    text = open(fp, encoding="utf-8").read()
    secs = get_sections(text)
    if not secs:
        continue
    n_sec += 1
    got = []
    for s in secs:
        got += parse_section(s)
    joined = "\n".join(secs)
    if "巅峰赛场" in joined and not got:
        miss.append((r, joined))
print("articles with 战报 section:", n_sec)
print("section has 巅峰赛场 but extracted nothing:", len(miss))
for r, s in miss[:15]:
    print("=" * 70)
    print(r["date"], r["title"][:50])
    print(s[:700])
