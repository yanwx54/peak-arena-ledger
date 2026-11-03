# 项目长期笔记：PeakArena Ledger

## 定位与归档
- 公众号「鸡坛快迅」《华府卫视战报》「巅峰赛场」战绩：抓取 → 出表 → 飞书/GitHub 同步。
- 仓库 `D:\WorkSpace\Project08_peak-arena-ledger`（main）；GitHub https://github.com/yanwx54/peak-arena-ledger（public，SSH）。
- 源工作区 `C:\Users\yanwx\WorkBuddy AI\2026-09-21-15-51-24`（权威备份源，数据异常时从此恢复）。
- 定时任务：每天 10:00，id `78b54c67-529e-4838-8a4a-b2bf27e3dbae`，跑 `peak-arena-ledger/daily_update.py`（全链路一条命令）。
- 逐轮执行明细见 `.workbuddy-ai/memory/automations/<id>/memory.md`。

## 飞书
- folder_token `KqwPfr0srlR6qedsdP9czMfxnng`；台账 file_token `LiiKbN6PXo9Bk6xxPx0ciuTLnVh`（`--file-token` 覆盖上传，链接恒定）。
  台账链接：https://mcnwra533zzy.feishu.cn/file/LiiKbN6PXo9Bk6xxPx0ciuTLnVh
- 配置 `deploy/feishu.json`（gitignore，勿改）。
- lark-cli：`C:\Users\yanwx\.workbuddy\binaries\node\cli-connector-packages\lark-cli.cmd`（是 `.workbuddy`，不是 `.workbuddy-ai`）。
- **身份坑（2026-11-03 踩过）**：bot（应用）身份常缺 `drive:file:upload` 这类「应用身份权限」→ 报
  `app_scope_not_applied / code 99991672`（错误里带开放平台 `console_url` 申请页）；
  `auth scopes` 里能看到 `drive:file:upload` 但那只是**用户授权**列表，不代表 bot 能用。
  user 身份 token 过期 → `need_user_authorization` / `token_missing`。
  **解法**：`reconnect_plugin` 重新授权飞书 connector（会刷新 user token，refresh_token 约 7 天有效）。
  流水线已固化：先试自动身份 → 失败再 `--as user` 兜底；且**飞书失败不阻断 Git 提交**（飞书是分发渠道、Git 是数据落盘）。

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
- **站点会迁服**（2026-10-27~29）：旧 IP `45.136.15.27`（用到 10-26 19:56）→ 新 IP `207.57.135.129`（HK，AS139659 LUCIDACLOUD，10-29 16:42 起）。
  新 IP **从本机网络被静默丢包**（443/80/8080/8443 全 timeout、ping 100% 丢、**无 RST**；对照腾讯云 HK 节点返回 RST）。
  → 遇到"连不上"先用 OTX passive DNS 查历史 IP，别直接判定成 Cloudflare 拦人或脚本问题。
- 判「滞后」三条：① 作者页 `/author?id=gh_72517d36a4d7&cycle=YYYYMM` 的「共找到 N 条记录」；② 首页热文流最新时间戳（区分全站滞后 vs 本号滞后）；③ 无 cookie 返回 ~4KB 验证页 / 带 cookie ~105–145KB 正常页。
- **「逐字节一致」≠ 上游没更新**，也可能是自己的枚举范围到期失效（2026-10-09 曾因月份写死只到 9 月丢 7 场）→ 报一致前必手工抽查**当月**作者页。现已改 `month_cycles()` 按 `date.today()` 生成。
- 作者页单页上限 30 条，`list_articles.py` 按 `page ≤ 6` 分页。
- `upstream_freshness()` 写 `upstream`(stale/updated) 与 `upstream_site` 字段；重跑对上游滞后无效，>3 天不收录才考虑备选源。
- 公众号已更新 ≠ 归档站已收录；**用户口述/截图是一手来源，可作补录依据**。
- **挑战只针对内容路径**：`/author`、`/art` 会跳 `/verify?redirect=`（非浏览器客户端拿不到）；`/`、`/index?page=N` 不拦，但只有标题+链接、无正文摘要。
- 备用出口排查：smzdm 转载停在更早内容；tianyancha 镜像只索引旧文；搜索引擎未收录该号战报 → **站点本身是唯一来源**，别的路都堵死。

## 备用源：搜狗微信 → 微信公众号原文（2026-11-03 新增，主源被封时的生命线）
- `sogou_fetch.py` 抓正文，`merge_sources.py` 并入 `data/articles_list.json`。
- 通路：`weixin.sogou.com/weixin?type=2&query=` → 跳转页 JS 壳 → 还原 `mp.weixin.qq.com/s?src=11&...` 签名 URL → 取原文。
- **会话建立必须先访问搜索结果页再访问首页**；只访问首页会缺 `SNUID`/`ABTEST`，`/link` 直接跳 `/antispider/`。
- 跳转页需拼接所有 `url += '...'` 片段 + 处理 `url.replace("@","")`；拼接偶发 `mp.weixin.qq.comom` 瑕疵要 replace 回去。
- 微信原文关键字段：`var msg_title` / `var ct` / `var user_name` / `var biz` / `var mid` / `var idx`；正文容器 `id="js_content"`（止于 `rich_media_area_extra`）。
- 稳定 ID = `md5(biz|mid|idx)`（32 位 hex），与 wxredian 的 id 形态一致。
- **判重双键**（`merge_sources.norm_title`）：标题归一化 **或** 同一天已有该号文章。
  归一化 = 去「鸡坛快迅：」前缀 + 全角半角标点统一 + 剥离所有标点空白 + 转小写。
  日期键是必需的：10-27 搜狗写「迷你6杀AK」而主源写「迷你7杀AK」，归一化对不上。
- 幂等：重跑条数与内容不变；主源恢复收录同一篇时自动收敛，不会双份计数。
- 抓取窗口 = 已合并清单最新日**回溯 7 天**（主源不可达时最新当天恰是缺口）。

## 搜狗限流识别（不识别的后果很严重）
- 限流特征：搜索页返回约 **5.3KB 空壳页**，无 `<li id="sogou_vr_11002601_box_">` 条目（正常 >30KB）。
- `harvest.py` 的 `is_limited()` 命中后**不写盘**、退出码 2；`daily_update.py` 识别退出码 2 报「本轮被限流」。
  **绝不能把限流当成「上游无新增」**——那会静默漏抓。
- `harvest.py` 已改「与既有结果合并」而非覆盖（曾因覆盖式写盘把 132 条写成 20 条，丢了 10 月全部新文章）。
  `data/*.bak.*` 已进 .gitignore。
- 查询词从 7 个扩到 **15 个**（新增「华府战报」「巅峰赛场 BO7」「鸡坛快迅 战报」等），只靠前 7 个词会漏 11-03 那一期。
- `mid` 是**全平台共享自增序列**（10-24→11-03 跨度 117，本号只占 8 篇）→ **不能用 mid 差值推断本号停更**。

## 已知故障模式（按此顺序排查，别乱改代码）
- **`title='wxredian.com' links=0` 且耗时 150s**：2026-10-30 起误判为"Turnstile 不过"，实为**网络层连不上**（Chrome 错误页标题就是主机名）。
  `cdp.py` 已修：识别 `chrome-error://` / `ERR_` 立即中止（~30s）并打印解析 IP + TCP 探测结论。
  **先看这条，别再空等 150s**。
- **飞书上传 99991672 / app_scope_not_applied**：不是脚本问题，是 lark-cli 身份问题 → 见「飞书」节的 `reconnect_plugin` 解法。
- **搜狗搜索返回 5.3KB 空壳页**：限流 → 保留既有清单，下次自动续抓，别手工清 `search_results.json`。
- `No module named websocket`：托管解释器依赖被周期性重置 → `pip install websocket-client openpyxl` 后重跑。此失败在 cookie 步骤前中止，`data/` 安全。
- CDP `403 Forbidden ... Rejected an incoming WebSocket connection`：9222 被别的项目残留 Chrome 抢占（如 scplayer-stats）→ `cdp.py` 已改 `_free_port()` 动态端口 + `suppress_origin=True`。
- `ConnectionAbortedError [WinError 10053]`：Chrome 崩了一次，直接重跑。
- xlsx 被 Excel/WPS 打开 → `WinError 5`：`commit_tmp()` 已重试 3 次→直接覆盖写入。
- 本机 ad-hoc 探测偶发 DNS `getaddrinfo failed`：以脚本的 `upstream_site` 为准。
- `cdp.py` 环境变量：`CDP_PROFILE`（换 profile）、`CDP_FORCE_IP`（强制域名→指定 IP，迁服时用）、
  `CDP_PROXY`（`--proxy-server`，Chrome 不认 http_proxy 环境变量，必须显式注入）、`CDP_WAIT_MAX`（等待上限）。


## 手工补录机制
- 入口 `data/manual_records.json`（入库），字段同 `jd_records.json`。
- 合并点在 **`build_output.py` 出表时**（先合并再按去重键去重）；**不放 `extract_jd.py`**——那里整体覆盖 `jd_records.json`，补录混进去会让 `n_records` 恒 >0，静默绕过 0 值 guard。
- 归档站补收录后，同键的正式记录排序在前 → 手工条目自动收敛，`manual backfill: 0` 即生效。

## 当前数据状态
- 2026-01-05 ~ **2026-11-02**，**246 场**（原始记录 537 条，含 3 条手工补录）。
- 按月：1月17 / 2月16 / 3月23 / 4月35 / 5月24 / 6月25 / 7月31 / 8月20 / 9月27 / 10月26 / 11月2。
- 比赛日 10-15 空缺属**源头缺失**（该期战报无「巅峰赛场」栏目），非漏抓。
- 比赛日 10-29 ~ 11-01 空缺属**源头停更**（线下赛期间该号停发，多组独立查询交叉验证过），非漏抓。
- `articles_list.json` 320 条（主源 312 + 备源 8）；`search_results.json` 140 条（鸡坛快迅 54 条，01-29 ~ 11-03）。
