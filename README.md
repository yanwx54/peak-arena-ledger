# PeakArena Ledger

**华府卫视 · 巅峰赛场 战绩台账（2026）**

把微信公众号「鸡坛快迅」每期《华府卫视战报》里「巅峰赛场」这一栏的战绩，一期一期捞出来、解析、去重，沉淀成一份可核对、能直接用的台账。

- 项目名：**PeakArena Ledger**（`PeakArena` = 巅峰赛场，`Ledger` = 台账）
- 仓库 / 工程目录：`peak-arena-ledger/`
- 当前数据范围：**2026-01-05 ~ 2026-09-18，共 204 场**

---

## 一、数据来源

| 项 | 值 |
| --- | --- |
| 公众号 | 鸡坛快迅 |
| 栏目 | 【华府卫视战报】→「巅峰赛场」子条目 |
| 归档站 | wxredian.com 作者页 `id=gh_72517d36a4d7` |
| 原文源 | `mp.weixin.qq.com`（正文在 `<div id="js_content">`） |
| 文章总量 | 277 篇（2025-12-01 ~ 2026-09-20 归档） |

## 二、数据口径（重要）

1. **比赛日 = 战报发布日 − 1 天**。战报标题为「昨日战报」，正文写的是前一天的比赛，因此统一回退一天记为比赛日。
2. **只取「巅峰赛场」条目**。同一期战报里还有别的子栏目（如其它对阵、表演赛），不在统计范围内。
3. **去重键** = `(比赛日, 选手1, 比分, 选手2)`。同一场比赛可能在多期推文里被重复提及，重复的只留一条。
4. **比分取 4:x / 3:x 等主赛制结果**，文中叙述性的片段比分（如「一度 2:1 领先」）不计入。
5. 起算日：**2026-01-01**（筛选条件 `match_date >= 2026-01-01`）。

## 三、目录结构

```
.
├── README.md                                  # 本文件
├── 华府卫视巅峰赛场战绩_2026.xlsx              # 成果：Excel 台账（主交付物）
├── 华府卫视巅峰赛场战绩_2026.html              # 成果：网页版台账
├── 华府卫视巅峰赛场战绩_2026.csv               # 成果：CSV（便于二次处理）
├── .华府卫视巅峰赛场战绩_2026.ref/
│   └── build.py                               # 生成 xlsx（openpyxl）
└── peak-arena-ledger/                         # 工程目录（原 jitan/）
    ├── cdp.py                                 # 用本机 Chrome + CDP 过 Cloudflare 验证，取 cookie
    ├── list_articles.py                       # 按月 + 分页枚举全部文章列表
    ├── fetch_all.py                           # 抓取 277 篇正文
    ├── extract_jd.py                          # 解析「巅峰赛场」战绩（核心）
    ├── build_output.py                        # 生成 CSV / MD / HTML
    ├── diag.py                                # 遗漏自检
    ├── harvest.py / fetch_articles.py         # 早期搜狗方案（已废弃，留档）
    ├── data/
    │   ├── cookies.json                       # wxredian cookie（有效期约 1 天）※不入库
    │   ├── articles_list.json                 # 277 篇文章元数据（含原文链接）
    │   ├── jd_records.json                    # 解析出的 451 条原始记录
    │   └── articles/<id>.txt                  # 277 篇正文 ※不入库（第三方内容）
    └── output/                                # 中间产物 CSV / MD / HTML
```

## 四、流水线

```
cdp.py            过 Cloudflare Turnstile，拿 WXREDIAN cookie
   ↓
list_articles.py  按月分页枚举 → data/articles_list.json（277 篇）
   ↓
fetch_all.py      逐篇抓正文 → data/articles/<id>.txt
   ↓
extract_jd.py     双策略解析「巅峰赛场」→ data/jd_records.json（451 条原始记录）
   ↓
build_output.py   按 2026 起算 + 去重 → output/巅峰赛场战绩_2026.csv（204 场）
   ↓
.ref/build.py     生成 华府卫视巅峰赛场战绩_2026.xlsx
```

### 解析器要点（`extract_jd.py`）

- **章节定位**：`【\s*华府卫视[^】]{0,10}战报\s*】`
- **条目名判定**：取条目第一行判断是否含「巅峰赛场」，避免 `巅峰赛场 bo7` 换行后战绩另起一行时被漏掉。
- **双策略提取**：
  1. 编号条目（`^\s*\d+\s*[、\.．,，]\s*`）内整行严格匹配 `选手A 比分:比分 选手B`；
  2. 「巅峰赛场」行锚点向下连续读最多 3 行，**遇到新编号条目立即停止**，防止跨条目串数据。
- **误抓过滤**：整行匹配 + 行长度 ≤ 34 + 叙述词黑名单（`度/领先/拿下/大胜/险胜/淘汰/一度/开局/扳回/…`）。
- **自检**：`diag.py` 校验「含巅峰赛场条目但没提取到战绩」的遗漏数为 **0**。

## 五、成果文件

| 文件 | 说明 |
| --- | --- |
| `华府卫视巅峰赛场战绩_2026.xlsx` | 两个 sheet：「巅峰赛场战绩」+「数据说明」。冻结表头、自动筛选、条带样式。 |
| `华府卫视巅峰赛场战绩_2026.html` | 单文件网页版，可直接分享查看。 |
| `华府卫视巅峰赛场战绩_2026.csv` | 纯数据，便于导入其它工具。 |

## 六、复现 / 更新

```bash
# 1. 取 cookie（需本机装了 Chrome，会弹出一个有界面的窗口，手动过验证）
python peak-arena-ledger/cdp.py

# 2. 枚举文章列表
python peak-arena-ledger/list_articles.py

# 3. 抓正文
python peak-arena-ledger/fetch_all.py

# 4. 解析 + 生成 CSV
python peak-arena-ledger/extract_jd.py
python peak-arena-ledger/build_output.py

# 5. 生成 xlsx
python ".华府卫视巅峰赛场战绩_2026.ref/build.py"
```

> 注：`cookies.json` 里的 `WXREDIAN` cookie 有效期约 1 天，重跑抓取前需要重新执行第 1 步。
> 解析与输出（第 4、5 步）是纯本地操作，不依赖网络，随时可重跑。
>
> **新克隆的仓库里没有 `data/articles/`**（第三方正文不入库），要重跑第 4 步必须先执行第 1–3 步把正文抓回来。

## 七、已知边界

- **源头缺期不算漏抓**：2 月中旬春节、3/15–3/20、5/26–6/2 等空档，经核对是源头本身当期没推文或当天无「巅峰赛场」，不是解析遗漏。
- **选手名保留原文**：中英文混用（如 `解冻`、`迷糊`、`侠义`、`爆炸头`）按推文原样记录，未做统一译名。
- **归档站覆盖**：wxredian 的归档止于 2026-09-20，之后的新期需要重新抓。

## 八、自动化与外部同步

### 每日 10:00 定时更新

一条命令跑完全链路：

```bash
python peak-arena-ledger/daily_update.py
```

流程：刷新 wxredian cookie（本机 Chrome 过 Cloudflare）→ 枚举文章 → 抓正文 → 解析战绩
→ 生成 CSV/MD/HTML → 生成 xlsx → 覆盖上传飞书 → 提交并推送 GitHub。

可选参数：`--skip-cookie`（沿用现有 cookie）、`--skip-feishu`、`--skip-git`。
没有新数据时不会产生空提交。

> 已配置定时任务每天 10:00 自动执行。

### 飞书同步

台账以**覆盖上传**方式同步到飞书云空间「PeakArena Ledger 战绩台账」文件夹。
上传时固定传 `--file-token`，因此文件链接恒定，不会每天堆出新文件。

飞书 `folder_token` / `file_token` 存在 `deploy/feishu.json`（已 gitignore，不入库）。

### GitHub

远程：`git@github.com:yanwx54/peak-arena-ledger.git`（SSH）。
