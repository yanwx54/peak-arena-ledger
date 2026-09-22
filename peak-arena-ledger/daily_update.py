# -*- coding: utf-8 -*-
"""PeakArena Ledger 每日更新流水线。

流程：刷新 cookie → 枚举文章 → 抓正文 → 解析 → 出表 → 上传飞书 → 提交推送 GitHub。

用法：
    python peak-arena-ledger/daily_update.py [--skip-cookie] [--skip-feishu] [--skip-git]

设计要点：
- 各步骤失败会立即中止并给出明确原因，不做静默降级。
- 飞书 / Git 配置缺失时跳过对应步骤并告警，不影响台账生成。
- 全程幂等：没有新数据时不会产生空提交。
"""
import argparse
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/peak-arena-ledger
ROOT = os.path.dirname(HERE)                               # <repo>
CSV = os.path.join(HERE, "output", "巅峰赛场战绩_2026.csv")
XLSX = os.path.join(ROOT, "华府卫视巅峰赛场战绩_2026.xlsx")
FEISHU_CFG = os.path.join(ROOT, "deploy", "feishu.json")
XLSX_BUILDER = os.path.join(ROOT, ".华府卫视巅峰赛场战绩_2026.ref", "build.py")

# lark-cli 由 WorkBuddy 飞书 connector 提供，位置随版本变动，按候选路径探测
LARK_CLI_CANDIDATES = [
    os.path.expandvars(r"%USERPROFILE%\.workbuddy\binaries\node\cli-connector-packages\lark-cli.cmd"),
    os.path.expandvars(r"%USERPROFILE%\.workbuddy\binaries\node\cli-connector-packages\lark-cli"),
]

log_lines = []


def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)


def run(cmd, cwd=HERE, label=None):
    """跑子进程，失败即抛错。返回 stdout。"""
    if label:
        log(f"[步骤] {label}")
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        log(f"  ✗ 失败（退出码 {p.returncode}）")
        for line in out.strip().splitlines()[-15:]:
            log("    " + line)
        raise RuntimeError(f"{label or cmd[0]} 失败")
    return out


def find_lark_cli():
    for p in LARK_CLI_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def git(args, check=True):
    p = subprocess.run(["git", "-C", ROOT] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {(p.stderr or '').strip()}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-cookie", action="store_true", help="跳过 cookie 刷新，用现有 cookie")
    ap.add_argument("--skip-feishu", action="store_true")
    ap.add_argument("--skip-git", action="store_true")
    args = ap.parse_args()

    result = {"status": "ok", "matches": None, "latest": None, "feishu": None, "git": None}

    # ---------- 1. 刷新 wxredian cookie ----------
    if args.skip_cookie:
        log("[步骤] 跳过 cookie 刷新（--skip-cookie）")
    else:
        run([sys.executable, "cdp.py"], label="刷新 wxredian cookie（本机 Chrome 过 Cloudflare）")
        log("  ✓ cookie 已更新")

    # ---------- 2~5. 抓取与解析 ----------
    out = run([sys.executable, "list_articles.py"], label="枚举文章列表")
    for line in out.strip().splitlines()[-3:]:
        log("  " + line)

    run([sys.executable, "fetch_all.py"], label="抓取文章正文")

    out = run([sys.executable, "extract_jd.py"], label="解析「巅峰赛场」战绩")
    for line in out.strip().splitlines()[:1]:
        log("  " + line)

    out = run([sys.executable, "build_output.py"], label="生成 CSV / MD / HTML")
    for line in out.strip().splitlines():
        log("  " + line)
        if line.startswith("records:"):
            result["matches"] = int(line.split(":")[1].strip())
        if line.startswith("date range:"):
            result["latest"] = line.split("~")[-1].strip()

    # ---------- 6. 生成 xlsx ----------
    out = run([sys.executable, XLSX_BUILDER], cwd=ROOT, label="生成 xlsx 台账")
    for line in out.strip().splitlines()[-2:]:
        log("  " + line)

    # ---------- 7. 上传飞书 ----------
    if args.skip_feishu:
        log("[步骤] 跳过飞书上传（--skip-feishu）")
    elif not os.path.exists(FEISHU_CFG):
        log(f"[步骤] 跳过飞书上传：缺少配置 {FEISHU_CFG}")
        result["feishu"] = "skipped:no-config"
    else:
        lark = find_lark_cli()
        if not lark:
            log("[步骤] 跳过飞书上传：未找到 lark-cli")
            result["feishu"] = "skipped:no-cli"
        else:
            cfg = json.load(open(FEISHU_CFG, encoding="utf-8"))
            log("[步骤] 覆盖上传台账到飞书云空间")
            # --file 只接受 cwd 下的相对路径，故以 ROOT 为 cwd
            rel = os.path.relpath(XLSX, ROOT).replace("\\", "/")
            out = run([lark, "drive", "+upload", "--file", "./" + rel,
                       "--folder-token", cfg["folder_token"],
                       "--file-token", cfg["file_token"], "--format", "json"],
                      cwd=ROOT, label=None)
            try:
                data = json.loads(out[out.index("{"):])["data"]
                result["feishu"] = data["url"]
                log(f"  ✓ 已上传：{data['url']}（version {data.get('version')}）")
            except Exception:
                log("  ✓ 已上传（未能解析返回）")
                result["feishu"] = "uploaded"

    # ---------- 8. 提交并推送 ----------
    if args.skip_git:
        log("[步骤] 跳过 Git 提交（--skip-git）")
    else:
        log("[步骤] 提交并推送 GitHub")
        git(["add", "-A"])
        if git(["diff", "--cached", "--quiet"], check=False).returncode == 0:
            log("  · 无变更，跳过提交")
            result["git"] = "no-change"
        else:
            n = result["matches"]
            latest = result["latest"] or ""
            msg = f"chore(data): 同步 {latest}（共 {n} 场）"
            git(["commit", "-q", "-m", msg])
            log(f"  ✓ 已提交：{msg}")
            p = git(["push"], check=False)
            if p.returncode == 0:
                log("  ✓ 已推送")
                result["git"] = "pushed"
            else:
                log("  ! 推送失败（本地已提交，未丢失）")
                for line in (p.stderr or "").strip().splitlines()[-5:]:
                    log("    " + line)
                result["git"] = "commit-only"

    log("")
    log("=== 完成 ===")
    log(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("")
        log(f"=== 中止：{e} ===")
        sys.exit(1)
