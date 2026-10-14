# -*- coding: utf-8 -*-
"""生成最终成果：CSV / Markdown / HTML。"""
import json, os, csv, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

START = "2026-01-01"

recs = json.load(open(os.path.join(DATA, "jd_records.json"), encoding="utf-8"))

# ---------- 手工补录合并 ----------
# 上游归档站（wxredian）偶发滞后数天，滞后期间新战绩无法自动获取，台账会停在旧日期。
# data/manual_records.json 允许把用户从公众号原文读到的「巅峰赛场」条目手工补进来，
# 使台账不必干等归档站。
#
# 只在出表阶段合并（不动 jd_records.json），有两个好处：
#   1. jd_records.json 始终保持「解析产物」的纯净语义，daily_update.py 里那套
#      「0 值 / 缩水 20% 即回滚」的保护逻辑完全不受影响；
#   2. 归档站补收录后，正式解析出的记录与手工条目去重键相同，且解析结果排在前面，
#      因此正式数据自动优先生效，手工条目自动失效 —— 无需人工清理。
MANUAL = os.path.join(DATA, "manual_records.json")
if os.path.exists(MANUAL):
    try:
        _m = json.load(open(MANUAL, encoding="utf-8"))
        _manual = _m.get("records", []) if isinstance(_m, dict) else _m
        _have = {(r["match_date"], r["p1"], r["score"], r["p2"]) for r in recs}
        _added = 0
        for _r in _manual:
            _k = (_r.get("match_date"), _r.get("p1"), _r.get("score"), _r.get("p2"))
            if not all(_k) or _k in _have:
                continue
            _have.add(_k)
            recs.append(_r)
            _added += 1
        print("manual backfill:", _added)
    except Exception as _e:
        print("manual backfill skipped:", _e)

recs = [r for r in recs if r["match_date"] >= START]
recs.sort(key=lambda r: (r["match_date"], r["p1"]))

# 去重（同一日期同一对阵同一比分）
seen = set()
uniq = []
for r in recs:
    k = (r["match_date"], r["p1"], r["score"], r["p2"])
    if k in seen:
        continue
    seen.add(k)
    uniq.append(r)
recs = uniq

# CSV
csv_path = os.path.join(OUT, "巅峰赛场战绩_2026.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["日期", "选手1", "比分", "选手2", "战报发布日期", "战报标题"])
    for r in recs:
        w.writerow([r["match_date"], r["p1"], r["score"], r["p2"], r["pub"], r["title"]])

# Markdown
md = ["| 日期 | 选手1 | 比分 | 选手2 |", "| --- | --- | --- | --- |"]
for r in recs:
    md.append("| %s | %s | %s | %s |" % (r["match_date"], r["p1"], r["score"], r["p2"]))
open(os.path.join(OUT, "巅峰赛场战绩_2026.md"), "w", encoding="utf-8").write("\n".join(md))

# HTML
rows = "\n".join(
    "<tr><td>%s</td><td>%s</td><td class='sc'>%s</td><td>%s</td></tr>" %
    (r["match_date"], r["p1"], r["score"], r["p2"]) for r in recs)
html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>华府卫视「巅峰赛场」战绩（2026）</title>
<style>
 body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f7fa;margin:0;padding:28px;color:#1f2937}
 .wrap{max-width:760px;margin:0 auto;background:#fff;border-radius:14px;padding:26px 30px;box-shadow:0 2px 14px rgba(0,0,0,.06)}
 h1{font-size:20px;margin:0 0 6px}
 .sub{color:#6b7280;font-size:13px;margin-bottom:18px}
 table{border-collapse:collapse;width:100%;font-size:14px}
 th,td{padding:7px 10px;border-bottom:1px solid #eef1f5;text-align:left}
 th{background:#f8fafc;color:#475569;font-weight:600}
 .sc{font-weight:700;color:#2563eb;font-variant-numeric:tabular-nums}
 tr:hover td{background:#f8fbff}
 .cnt{color:#6b7280;font-size:13px;margin-top:14px}
</style></head><body><div class="wrap">
<h1>华府卫视「巅峰赛场」战绩</h1>
<div class="sub">来源：微信公众号「鸡坛快迅」· 华府卫视战报 · 2026-01-01 起</div>
<table><thead><tr><th>日期</th><th>选手1</th><th>比分</th><th>选手2</th></tr></thead>
<tbody>
__ROWS__
</tbody></table>
<div class="cnt">共 __CNT__ 场</div>
</div></body></html>"""
html = html.replace("__ROWS__", rows).replace("__CNT__", str(len(recs)))
open(os.path.join(OUT, "巅峰赛场战绩_2026.html"), "w", encoding="utf-8").write(html)

print("records:", len(recs))
print("date range:", recs[0]["match_date"], "~", recs[-1]["match_date"])
import collections
print("by month:", dict(sorted(collections.Counter(r["match_date"][:7] for r in recs).items())))
print("csv:", csv_path)
