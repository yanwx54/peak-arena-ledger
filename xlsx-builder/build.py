# -*- coding: utf-8 -*-
"""生成《华府卫视巅峰赛场战绩（2026年）》xlsx。"""
import csv, datetime, json, os, re, time, zipfile

try:
    import openpyxl
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl>=3.1.0"])
    import openpyxl

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # 仓库根目录（本文件所在目录的上一级）

SRC = os.path.join(ROOT, "peak-arena-ledger", "output", "巅峰赛场战绩_2026.csv")
OUT = os.path.join(ROOT, "华府卫视巅峰赛场战绩_2026.xlsx")
TITLE = "华府卫视巅峰赛场战绩（2026年）"


def xl_color(css_hex: str) -> str:
    value = css_hex.removeprefix("#").upper()
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB, got: {css_hex}")
    return "FF" + value


XL_HEAD_BG = xl_color("#4472C4")
XL_HEAD_FG = xl_color("#FFFFFF")
XL_STRIPE = xl_color("#F2F6FC")
XL_BORDER = xl_color("#BFBFBF")
XL_NOTE_BG = xl_color("#EDF2FB")

thin = Side(style="thin", color=XL_BORDER)
border_bottom = Border(bottom=thin)

rows = []
with open(SRC, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append(r)

wb = Workbook()
wb.properties.title = TITLE
# 固定文档时间戳，保证「同样的数据 → 字节完全一致的 xlsx」。
# 否则每次生成都会内嵌新的 created/modified，导致每日同步在无数据变更时也产生空提交。
_FIXED_TS = datetime.datetime(2026, 1, 1, 0, 0, 0)
wb.properties.created = _FIXED_TS
wb.properties.modified = _FIXED_TS
wb.properties.creator = "PeakArena Ledger"
wb.properties.lastModifiedBy = "PeakArena Ledger"

# ---------- Sheet 1: 战绩明细 ----------
ws = wb.active
ws.title = "巅峰赛场战绩"

# 锚点：第1行标题、第2行表头、第3~206行数据
HEAD_ROW = 2
FIRST = 3
LAST = FIRST + len(rows) - 1

ws["A1"] = TITLE
ws["A1"].font = Font(size=14, bold=True, color=xl_color("#1F3864"))
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
ws.row_dimensions[1].height = 26

headers = ["序号", "日期", "选手1", "比分", "选手2"]
for c, h in enumerate(headers, 1):
    cell = ws.cell(row=HEAD_ROW, column=c, value=h)
    cell.font = Font(bold=True, color=XL_HEAD_FG)
    cell.fill = PatternFill("solid", fgColor=XL_HEAD_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = border_bottom
ws.row_dimensions[HEAD_ROW].height = 20

for i, r in enumerate(rows):
    rr = FIRST + i
    d = datetime.datetime.strptime(r["日期"], "%Y-%m-%d").date()
    ws.cell(row=rr, column=1, value=i + 1).alignment = Alignment(horizontal="center")
    c2 = ws.cell(row=rr, column=2, value=d)
    c2.number_format = "yyyy-mm-dd"
    c2.alignment = Alignment(horizontal="center")
    ws.cell(row=rr, column=3, value=r["选手1"]).alignment = Alignment(horizontal="left")
    sc = ws.cell(row=rr, column=4, value=r["比分"])
    sc.alignment = Alignment(horizontal="center")
    sc.font = Font(bold=True, color=xl_color("#2563EB"))
    ws.cell(row=rr, column=5, value=r["选手2"]).alignment = Alignment(horizontal="left")
    if i % 2 == 1:
        for c in range(1, 6):
            ws.cell(row=rr, column=c).fill = PatternFill("solid", fgColor=XL_STRIPE)

for col, w in zip("ABCDE", [6, 13, 14, 9, 14]):
    ws.column_dimensions[col].width = w

ws.freeze_panes = "A3"
ws.auto_filter.ref = "A%d:E%d" % (HEAD_ROW, LAST)

# ---------- Sheet 2: 数据说明 ----------
ws2 = wb.create_sheet("数据说明")
ws2.column_dimensions["A"].width = 16
ws2.column_dimensions["B"].width = 92
ws2["A1"] = "数据说明"
ws2["A1"].font = Font(size=13, bold=True, color=xl_color("#1F3864"))
ws2.merge_cells("A1:B1")
# 统计范围按实际数据动态生成。
# 此前写死为「2026-01-01 至 2026-09-18」+ 动态场次，随着台账增长，
# 该行与表格内容自相矛盾（表里已到 10 月，说明却停在 9 月）。
if rows:
    _scope = "%s 至 %s，共 %d 场「巅峰赛场」对局。" % (rows[0]["日期"], rows[-1]["日期"], len(rows))
else:
    _scope = "暂无数据。"

# 归档站收录滞后期间可能存在人工补录；仅在确有补录时追加说明行。
_MANUAL = os.path.join(ROOT, "peak-arena-ledger", "data", "manual_records.json")
try:
    _m = json.load(open(_MANUAL, encoding="utf-8"))
    _manual_n = len(_m.get("records", []) if isinstance(_m, dict) else _m)
except Exception:
    _manual_n = 0

notes = [
    ("数据来源", "微信公众号「鸡坛快迅」发布的「华府卫视昨日战报」，经 wxredian.com 归档逐篇抓取原文。"),
    ("统计范围", _scope),
    ("日期口径", "战报为次日发布，标题即「昨日战报」，故表中日期 = 战报发布日 − 1 天，即实际比赛日。"),
    ("抓取范围", "该公众号 2025-12 起的历史推文全量抓取，仅统计「华府卫视战报」中「巅峰赛场」条目的对局。"),
    ("说明", "同一日出现两行（如 bo7+bo3）时，为该日安排了两场巅峰赛场对局。"),
    ("数据更新", "由 peak-arena-ledger/daily_update.py 每日自动增量更新；具体变更见仓库提交记录。"),
]
if _manual_n:
    notes.insert(1, ("人工补录", "其中 %d 条因归档站收录滞后，按公众号原文人工补录"
                                 "（见 peak-arena-ledger/data/manual_records.json）；"
                                 "归档站补收录后会自动以解析结果为准。" % _manual_n))
for i, (k, v) in enumerate(notes):
    r = 3 + i
    a = ws2.cell(row=r, column=1, value=k)
    a.font = Font(bold=True)
    a.alignment = Alignment(vertical="top")
    a.fill = PatternFill("solid", fgColor=XL_NOTE_BG)
    b = ws2.cell(row=r, column=2, value=v)
    b.alignment = Alignment(vertical="top", wrap_text=True)

_FIXED_ZIP_DT = (2026, 1, 1, 0, 0, 0)
_FIXED_ISO = "2026-01-01T00:00:00Z"


def freeze_xlsx(path):
    """把 xlsx 内的所有时间戳冻结成固定值。

    openpyxl 保存时会把 docProps/core.xml 的 dcterms:modified 写成当前时间，
    zip 条目也各自带生成时刻，导致「数据没变、文件字节却变了」。
    每日同步据此判断有无变更，因此必须让同样数据产出字节一致的产物。
    """
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = re.sub(
                    rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>",
                    ('<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
                     % _FIXED_ISO).encode("utf-8"),
                    data)
            item.date_time = _FIXED_ZIP_DT
            zout.writestr(item, data)


def commit_tmp(tmp, path):
    """把冻结后的临时文件落到目标路径。

    台账是给人看的交付物，用户经常用 Excel / WPS 打开着它；此时 Windows 会
    拒绝 os.replace（WinError 5 拒绝访问），整个流水线会在这里无谓地中止。
    因此：短暂重试 → 仍失败则退化为直接覆盖写入 → 再失败才报出可操作的提示。
    """
    last = None
    for _ in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:
            last = e
            time.sleep(1.0)
    try:
        with open(tmp, "rb") as f:
            data = f.read()
        with open(path, "wb") as f:
            f.write(data)
        os.remove(tmp)
        print("  ! 目标文件被占用，已改为直接覆盖写入；建议关闭 Excel/WPS 后重新生成以确认。")
    except Exception:
        raise RuntimeError(
            "无法写入 %s：文件被其它程序占用（通常是 Excel / WPS 正打开着台账）。"
            "请关闭该文件后重跑。" % path) from last


wb.save(OUT)
freeze_xlsx(OUT)
commit_tmp(OUT + ".tmp", OUT)
print("saved:", OUT, "rows:", len(rows))
