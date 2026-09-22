# -*- coding: utf-8 -*-
"""从文章正文中提取【华府卫视战报】里的「巅峰赛场」战绩（v2）。"""
import re, json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ART = os.path.join(DATA, "articles")

rows = json.load(open(os.path.join(DATA, "articles_list.json"), encoding="utf-8"))

SEC = re.compile(r"【\s*华府卫视[^】]{0,10}战报\s*】")
ANY_HDR = re.compile(r"【[^】]{0,30}】")

NARRATIVE = ("度", "领先", "落后", "拿下", "获胜", "大胜", "险胜", "淘汰", "一度", "开局",
             "扳回", "双方", "比赛", "优势", "反超", "连胜", "连败", "两局", "三局", "四局",
             "第五", "第六", "决胜", "最终", "成功", "轻取", "零封", "喂蛋", "油条", "追",
             "比分", "取胜", "败", "胜", "负", "晋级", "出局", "结束", "横扫", "复仇", "送")

NAME = r"[A-Za-z0-9\u4e00-\u9fa5_\-\.\(\)（）]+"
LINE_MATCH = re.compile(r"^(" + NAME + r")\s*(\d+)\s*[:：\-–—]\s*(\d+)\s*(" + NAME + r")$")
MATCH = re.compile(r"(" + NAME + r")\s*(\d+)\s*[:：\-–—]\s*(\d+)\s*(" + NAME + r")")


def get_sections(text):
    out = []
    for m in SEC.finditer(text):
        start = m.end()
        nxt = ANY_HDR.search(text, start)
        out.append(text[start:nxt.start() if nxt else len(text)])
    return out


def strip_prefix(line):
    line = re.sub(r"^\s*\d+\s*[、\.．]\s*", "", line)
    line = line.replace("巅峰赛场", " ")
    line = re.sub(r"(?i)bo\s*\d+", " ", line)
    line = re.sub(r"[+＋]", " ", line)
    line = re.sub(r"[ \t\u3000]+", " ", line)
    return line.strip()


def is_match_line(line):
    if not line or len(line) > 34:
        return False
    m = LINE_MATCH.match(line)
    if not m:
        return False
    p1, p2 = m.group(1), m.group(4)
    if any(w in p1 for w in NARRATIVE) or any(w in p2 for w in NARRATIVE):
        return False
    return True


def parse_section(sec):
    """解析「华府卫视战报」中标记为「巅峰赛场」的条目"""
    res = []
    marks = [(m.start(), m.end(), int(m.group(1)))
             for m in re.finditer(r"(?m)^\s*(\d+)\s*[、\.．,，]\s*", sec)]

    def emit(ln):
        if is_match_line(ln):
            m = LINE_MATCH.match(ln)
            res.append((m.group(1).strip(), m.group(2), m.group(3), m.group(4).strip()))
            return True
        ms = MATCH.findall(ln)
        if len(ms) >= 2:
            leftover = MATCH.sub("", ln).strip(" 　:：,，.。、")
            if len(leftover) <= 2:
                for g in ms:
                    res.append((g[0].strip(), g[1], g[2], g[3].strip()))
                return True
        return False

    # 方式一：编号条目
    for i, (s, e, num) in enumerate(marks):
        body_end = marks[i + 1][0] if i + 1 < len(marks) else len(sec)
        body = sec[e:body_end]
        if "巅峰赛场" not in body.split("\n")[0]:
            continue
        for ln in [strip_prefix(sec[s:e])] + [strip_prefix(l) for l in body.split("\n")]:
            emit(ln)

    # 方式二：以「巅峰赛场」行作为锚点，向下连续读取对局行（遇到新编号条目即停）
    NUM = re.compile(r"^\s*\d+\s*[、\.．,，]\s*")
    lines = sec.split("\n")
    for i, ln in enumerate(lines):
        if "巅峰赛场" not in ln:
            continue
        emit(strip_prefix(ln))
        run = 0
        for j in range(i + 1, min(i + 6, len(lines))):
            raw = lines[j]
            if NUM.match(raw):
                break
            if emit(strip_prefix(raw)):
                run += 1
                if run >= 3:
                    break
            else:
                break
    return res


def main():
    out = []
    nofile = []
    stats = {"has_sec": 0, "has_jd": 0}
    for r in sorted(rows, key=lambda x: x["date"]):
        fp = os.path.join(ART, r["id"] + ".txt")
        if not os.path.exists(fp):
            nofile.append(r["id"])
            continue
        text = open(fp, encoding="utf-8").read()
        secs = get_sections(text)
        if secs:
            stats["has_sec"] += 1
        got = []
        for s in secs:
            got += parse_section(s)
        if got:
            stats["has_jd"] += 1
        pub = datetime.datetime.strptime(r["date"], "%Y-%m-%d %H:%M")
        md = (pub - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        for (p1, s1, s2, p2) in got:
            out.append({"match_date": md, "pub": r["date"][:10], "p1": p1,
                        "score": "%s:%s" % (s1, s2), "p2": p2,
                        "title": r["title"], "id": r["id"]})

    json.dump(out, open(os.path.join(DATA, "jd_records.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("records:", len(out), "| nofile:", len(nofile), "|", stats)
    for o in out:
        print("%s  %s %s %s   [pub %s]" % (o["match_date"], o["p1"], o["score"], o["p2"], o["pub"]))


if __name__ == "__main__":
    main()
