# 项目长期笔记：PeakArena Ledger

## 项目定位
微信公众号「鸡坛快迅」《华府卫视战报》→「巅峰赛场」战绩的抓取 + 归档 + 台账工具链。

## 归档位置
- **本地仓库**：`D:\WorkSpace\Project08_peak-arena-ledger`（分支 `main`）
- **GitHub**：https://github.com/yanwx54/peak-arena-ledger （public，远程用 SSH）
- 原工作区：`C:\Users\yanwx\WorkBuddy AI\2026-09-21-15-51-24`
- 后续改动记得同步回仓库并提交。

## 自动化与外部同步
- **定时任务**：每天 10:00，自动化 id `78b54c67-529e-4838-8a4a-b2bf27e3dbae`，
  cwd = 仓库目录，跑 `peak-arena-ledger/daily_update.py`（全链路一条命令）。
- **飞书**：云空间文件夹「PeakArena Ledger 战绩台账」
  - folder_token `KqwPfr0srlR6qedsdP9czMfxnng`
  - 台账 file_token `LiiKbN6PXo9Bk6xxPx0ciuTLnVh`（`--file-token` 覆盖上传，链接恒定）
  - 配置存 `deploy/feishu.json`（已 gitignore，不入库）
  - `lark-cli` 路径：`C:\Users\yanwx\.workbuddy\binaries\node\cli-connector-packages\lark-cli.cmd`
    （注意是 `.workbuddy`，不是 `.workbuddy-ai`）
- **GitHub 建仓**：WorkBuddy 的 GitHub connector 无建仓权限，需用 `git credential fill`
  的 token 直连 api.github.com 且**绕过沙箱**。详见技能 `archive-project-to-github`。

## 数据口径（改动前必确认）
1. **比赛日 = 战报发布日 − 1 天**（战报标题为「昨日战报」）
2. 只取「巅峰赛场」条目，同期的其它子栏目不算
3. 去重键 = `(比赛日, 选手1, 比分, 选手2)`
4. 比分取主赛制结果，文中叙述性片段比分（「一度 2:1 领先」）不计入
5. 起算日 2026-01-01；实际首场 2026-01-05

## 关键约定
- 脚本一律用 `os.path.dirname(os.path.abspath(__file__))` 定位，**禁止硬编码绝对路径**（换盘符会写回旧目录）。
- `peak-arena-ledger/data/cookies.json` 是 wxredian 会话凭据（有效期约 1 天），**永远不入库**。
- 重跑抓取需先跑 `cdp.py` 过 Cloudflare（本机 headful Chrome + CDP）；解析与出表是纯本地操作，不依赖网络。
- **`cdp.py` 禁止固定 sleep 取 cookie**：wxredian 的 Turnstile 实测要 ~17 秒才通过（曾写死 12s 导致偶发失效），
  必须轮询到「验证页消失 + 能取到文章链接」再落盘，并用该 cookie 实测校验一次。
- **抓取类流水线必须防「0 值清空」**：枚举/解析为 0 时覆盖式写盘会毁掉好数据。
  `daily_update.py` 已实现每轮备份 `data/.backup/` + 0 值回滚中止。
- **源工作区是权威副本**：仓库侧数据异常时从 `C:\Users\yanwx\WorkBuddy AI\2026-09-21-15-51-24\peak-arena-ledger` 恢复。
- `build.py` 用 `freeze_xlsx()` 冻结 xlsx 时间戳，保证同样数据产出字节一致，避免每日空提交。

## 当前数据状态
- 2026-01-05 ~ 2026-09-18，**204 场**（原始记录 451 条）
- 按月：1月17 / 2月16 / 3月21 / 4月35 / 5月24 / 6月25 / 7月31 / 8月20 / 9月15
- wxredian 归档止于 2026-09-20，之后新期需重新抓取
