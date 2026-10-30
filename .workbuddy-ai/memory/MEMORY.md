# 项目长期笔记：PeakArena Ledger

## 定位与归档
- 公众号「鸡坛快迅」《华府卫视战报》「巅峰赛场」战绩：抓取 → 出表 → 飞书/GitHub 同步。
- 仓库 `D:\WorkSpace\Project08_peak-arena-ledger`（main）；GitHub https://github.com/yanwx54/peak-arena-ledger（public，SSH）。
- 源工作区 `C:\Users\yanwx\WorkBuddy AI\2026-09-21-15-51-24`（权威备份源，数据异常时从此恢复）。
- 定时任务：每天 10:00，id `78b54c67-529e-4838-8a4a-b2bf27e3dbae`，跑 `peak-arena-ledger/daily_update.py`（全链路一条命令）。
- 逐轮执行明细见 `.workbuddy-ai/memory/automations/<id>/memory.md`。

## 飞书
- folder_token `KqwPfr0srlR6qedsdP9czMfxnng`；台账 file_token `LiiKbN6PXo9Bk6xxPx0ciuTLnVh`（`--file-token` 覆盖上传，链接恒定）。
- 配置 `deploy/feishu.json`（gitignore，勿改）。
- lark-cli：`C:\Users\yanwx\.workbuddy\binaries\node\cli-connector-packages\lark-cli.cmd`（是 `.workbuddy`，不是 `.workbuddy-ai`）。

## 数据口径（改动前必确认）
1. 比赛日 = 战报发布日 − 1 天（标题为「昨日战报」）
2. 只取「巅峰赛场」，同期其它子栏目不算
3. 去重键 `(match_date, p1, score, p2)`
4. 比分取主赛制结果，文中叙述性片段（「一度 2:1 领先」）不计
5. 起算 2026-01-01；实际首场 2026-01-05

## 关键约定
- 脚本用 `os.path.dirname(os.path.abspath(__file__))` 定位，**禁止硬编码绝对路径**。
- `data/cookies.json` 是 wxredian 会话凭据（约 1 天有效），**永远不入库**。
- 抓取需 `cdp.py` 过 Cloudflare（本机 headful Chrome + CDP）；解析/出表纯本地。
- **`cdp.py` 禁止固定 sleep**：Turnstile 实测约 17s 通过，须轮询到「验证页消失 + 能取到文章链接」再落盘并实测校验（上限 150s）。
- **数据保护 guard**：每轮先备份 `data/.backup/`；枚举/解析为 0 或较上轮降幅 ≥20% 时自动回滚中止（2026-10-02 Cloudflare 半通过事故后补）。
- `xlsx-builder/build.py` 的 `freeze_xlsx()` 冻结时间戳，保证同数据字节一致，避免每日空提交。
- 根目录 CSV/HTML 是对外交付物，`daily_update.py` 自动从 `output/` 复制同步。
- 解析器须兼容表头变体：`【\s*华府(?:卫视)?[^】]{0,10}战报\s*】`，无表头时以 `N、巅峰赛场` 兜底。新写法出现要同步扩展，否则整段静默跳过。
- `diag.py` 双检查：段内遗漏 + 整段未匹配（全文含「巅峰赛场」却零解析）；A/B 均应为 0。

## 上游归档站 wxredian
- 第三方公众号归档站，收录节奏自控：通常滞后 1~2 天，偶发 3 天+。
- 判「滞后」三条：① 作者页 `/author?id=gh_72517d36a4d7&cycle=YYYYMM` 的「共找到 N 条记录」；② 首页热文流最新时间戳（区分全站滞后 vs 本号滞后）；③ 无 cookie 返回 ~4KB 验证页 / 带 cookie ~105–145KB 正常页。
- **「逐字节一致」≠ 上游没更新**，也可能是自己的枚举范围到期失效（2026-10-09 曾因月份写死只到 9 月丢 7 场）→ 报一致前必手工抽查**当月**作者页。现已改 `month_cycles()` 按 `date.today()` 生成。
- 作者页单页上限 30 条，`list_articles.py` 按 `page ≤ 6` 分页。
- `upstream_freshness()` 写 `upstream`(stale/updated) 与 `upstream_site` 字段；重跑对上游滞后无效，>3 天不收录才考虑备选源。
- 公众号已更新 ≠ 归档站已收录；**用户口述/截图是一手来源，可作补录依据**。

## 已知故障模式（按此顺序排查，别乱改代码）
- `No module named websocket`：托管解释器依赖被周期性重置 → `pip install websocket-client openpyxl` 后重跑。此失败在 cookie 步骤前中止，`data/` 安全。
- CDP `403 Forbidden ... Rejected an incoming WebSocket connection`：9222 被别的项目残留 Chrome 抢占（如 scplayer-stats）→ `cdp.py` 已改 `_free_port()` 动态端口 + `suppress_origin=True`。
- `ConnectionAbortedError [WinError 10053]`：Chrome 崩了一次，直接重跑。
- xlsx 被 Excel/WPS 打开 → `WinError 5`：`commit_tmp()` 已重试 3 次→直接覆盖写入。
- 本机 ad-hoc 探测偶发 DNS `getaddrinfo failed`：以脚本的 `upstream_site` 为准。

## 手工补录机制
- 入口 `data/manual_records.json`（入库），字段同 `jd_records.json`。
- 合并点在 **`build_output.py` 出表时**（先合并再按去重键去重）；**不放 `extract_jd.py`**——那里整体覆盖 `jd_records.json`，补录混进去会让 `n_records` 恒 >0，静默绕过 0 值 guard。
- 归档站补收录后，同键的正式记录排序在前 → 手工条目自动收敛，`manual backfill: 0` 即生效。

## 当前数据状态
- 2026-01-05 ~ **2026-10-22**，**238 场**（原始记录 521 条，含 3 条手工补录）。
- 按月：1月17 / 2月16 / 3月23 / 4月35 / 5月24 / 6月25 / 7月31 / 8月20 / 9月27 / 10月20。
- 比赛日 10-15 空缺属**源头缺失**（该期战报无「巅峰赛场」栏目），非漏抓。
