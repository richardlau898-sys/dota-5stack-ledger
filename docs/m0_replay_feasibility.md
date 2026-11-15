# M0 · Replay Lab 可行性实测报告

> **核心结论**：真实 Dota 2（`patch=60` / 7.41）录像的下载、解压与 `odota/parser` 解析**完全可行**。3 场实测比赛全部解析成功且 100% 产出逐秒（`1 Hz`）英雄坐标与事件流；与 OpenDota `teamfights[].players[].deaths_pos`（`130/130`，100.0%）和 `players[].obs_log`（`112/112`，100.0%）精确对齐；GitHub Actions `ubuntu-latest` 单场匿名实测解析仅耗时 `4.972s`（`/usr/bin/time -v` 内存峰值 `649912 KB` ≈ `634.68 MiB`）。
>
> **规则遵循声明**：本报告所有标记为 **【实测】** 的数字均可在报告末尾附带的原始命令输出中原文找到；所有基于周均场次与实测均值推算的数据均明确标注 **【预估】** 与公式；Supabase 生产后台配额因无登录态与生产凭据无法观测，已按规则如实标注 **【做不到】** 与精确原因；所有公开代码、日志与样本已剔除玩家昵称、Steam/Account ID、`replay_url` 盐值、`chat` 及 `epilogue`。

---

## 1. 取样说明与环境选型（含 Rule 21 变更记录）

### 1.1 取样范围调整（Rule 21 已确认）
- **原规格要求**（见 `docs/project_replay_lab.md`）：3 场开赛在 3 天以内的车队最近比赛，且至少 1 场当前最新补丁。
- **【实测】近 72 小时场次不足**：截至 `2026-11-15T11:06:05Z`，遍历 `roster.json`（11 个账号、按 `account_aliases` 去重为 10 名成员）在 OpenDota 的记录，过去 `<= 3.00d` 内仅有 `1` 场已解析车队比赛（`9087090072`，约 `2.82d`），`[0.00d, 2.00d]` 为 `0` 场。
- **已获批准变更（Rule 21）**：经 Richard 确认将取样窗口放宽至 **`< 6 天`**，选用同属当前最新补丁 **`patch = 60`（7.41）** 的 3 场已解析车队比赛：

| 比赛号 | 开赛时间 (UTC) | 探测时刻距今 (实测) | 车队同边人数 (实测) | 补丁 | 比赛时长 (实测) | OpenDota 状态 |
|---|---|---|---|---|---|---|
| `9087090072` | `2026-11-12T15:30:07+00:00` | `2.82d` | 2 人 | `patch=60` (7.41) | `2616s` (`43m36s`) | `v22` |
| `9085834639` | `2026-11-11T15:56:51+00:00` | `3.80d` | 3 人 | `patch=60` (7.41) | `2567s` (`42m47s`) | `v22` |
| `9083213997` | `2026-11-09T15:12:11+00:00` | 推算 `5.83d` (`11-09 15:12Z -> 11-15 11:06Z`) | 5 人（5 黑） | `patch=60` (7.41) | `2481s` (`41m21s`) | `v22` |

### 1.2 `odota/parser` 构建方式与关键格式发现
- **构建方式选择：从源码构建（非 Docker）**。本地 macOS 宿主机无 Docker 与系统 JVM，采用在临时目录安装便携式 Temurin OpenJDK `21.0.13+9` 与 Apache Maven `3.9.9`（CI 上使用 Maven `3.9.15`），克隆 `https://github.com/odota/parser.git`（实测 commit `67945be040de92d0ba9cdedc77434886d4f736be`）执行 `mvn -q package -DskipTests` 生成 `target/stats-0.1.0.jar`（`29,090,157` 字节），并通过 `tools/replay_lab/ParseCli.java`（仅 27 行，调用 `new opendota.Parse(is, os, false)`）将本地 `.dem` 直接流式解析为 JSONL 文件。该方式同样直接复用于 GitHub Actions `ubuntu-latest`（免容器构建开销，全流程 1 分 51 秒完成）。
- **【实测】重要发现：Valve CDN 实际下发 `Zstandard` 而非 `Bzip2`**：
  - OpenDota 返回的 `replay_url` 后缀虽仍为 `.dem.bz2`，但 3 场实测下载载荷经 `file` 与文件头检测均为 **`Zstandard compressed data (v0.8+)`**（魔数 `\x28\xb5\x2f\xfd`，并非 `BZh`）。若直接调用 `bzip2 -dk` 会失败（`not a bzip2 file`）；这与 `odota/parser` 源码 `Main.java` 同时检测 Zstd/Bzip2 魔数一致。因此 `run_local_m0.py` 与 `gha_m0_bench.py` 均按魔数自动选用 `zstd -d -f`（兼容回退 `bzip2 -dk`），解压后 3 场文件头均为标准 Source 2 录像魔数 `PBDEMS2\x00`（hex `504244454d533200`）。

---

## 2. 本地 3 场实测：耗时、文件大小与事件类型

> 测试环境【实测】：`Darwin arm64`（macOS `26.6.2` Build `25G83`），`Apple M5 Pro`，`18` 逻辑核，内存 `25,769,803,776` 字节（`24.00 GiB`），Temurin JDK `21.0.13+9`，`zstd v1.5.7`。

### 2.1 各步骤耗时与内存占用【实测】

| 比赛号 | 下载 `.dem.bz2` | `zstd -d -f` 解压 | `ParseCli` 解析 Wall | `/usr/bin/time -l` CPU & Real | Mac 最大常驻内存 (`max_rss`) | Mac `peak_footprint` | 全量 `jsonl` `gzip -9` | `1Hz` 精简 JSON `gzip -9` |
|---|---|---|---|---|---|---|---|---|
| `9087090072` | `23.36s` | `0.09s` | `3.207s` | `3.20 real / 4.41 user / 0.39 sys` | `552,943,616 B` (`527.33 MiB`) | `552,977,656 B` (`527.36 MiB`) | `0.37s` | `0.057s` |
| `9085834639` | `2.272s` | `0.117s` | `2.768s` | `2.76 real / 3.94 user / 0.30 sys` | `554,729,472 B` (`529.03 MiB`) | `542,131,424 B` (`517.02 MiB`) | `0.344s` | `0.054s` |
| `9083213997` | `0.638s` | `0.11s` | `2.847s` | `2.83 real / 4.41 user / 0.36 sys` | `571,179,008 B` (`544.72 MiB`) | `560,825,616 B` (`534.84 MiB`) | `0.374s` | `0.051s` |

### 2.2 文件体积全链路对比【实测】

| 比赛号 | 压缩录像 `.dem.bz2` | 解压后 `.dem` | 全量解析 `.jsonl` | 全量 `jsonl.gz` (`-9`) | 1Hz 0.1精度坐标状态 `compact_01.json` | 1Hz 0.1精度压缩 `compact_01.json.gz` | 1Hz 整数cell压缩 `compact_int.json.gz` |
|---|---|---|---|---|---|---|---|
| `9087090072` | `54,071,426 B` (`51.57 MiB`) | `91,934,749 B` (`87.68 MiB`) | `52,966,593 B` (`50.51 MiB`) | `2,156,386 B` (`2.06 MiB`) | `526,678 B` (`514.33 KiB`) | `146,572 B` (`143.14 KiB`) | `107,641 B` (`105.12 KiB`) |
| `9085834639` | `52,132,535 B` (`49.72 MiB`) | `88,942,221 B` (`84.82 MiB`) | `43,807,456 B` (`41.78 MiB`) | `1,811,562 B` (`1.73 MiB`) | `517,093 B` (`504.97 KiB`) | `139,414 B` (`136.15 KiB`) | `101,970 B` (`99.58 KiB`) |
| `9083213997` | `54,316,047 B` (`51.80 MiB`) | `96,843,120 B` (`92.36 MiB`) | `48,143,894 B` (`45.91 MiB`) | `1,943,499 B` (`1.85 MiB`) | `489,973 B` (`478.49 KiB`) | `132,751 B` (`129.64 KiB`) | `97,092 B` (`94.82 KiB`) |
| **3 场算术均值** | `53,506,669 B` (`51.03 MiB`) | `92,573,363 B` (`88.29 MiB`) | `48,305,981 B` (`46.07 MiB`) | `1,970,482 B` (`1.88 MiB`) | `511,248 B` (`499.27 KiB`) | `139,579 B` (`136.31 KiB`) | `102,234 B` (`99.84 KiB`) |

### 2.3 解析输出主要事件类型与条数【实测】

三场总行数分别为 `210,452`（`9087090072`）、`175,988`（`9085834639`）、`222,945`（`9083213997`）。各关键事件条数如下（全部 60+ 种事件完整计数见附录 2 原始 JSON 输出）：

| 事件 `type` | `9087090072` | `9085834639` | `9083213997` | 用途说明（M1–M3 相关） |
|---|---|---|---|---|
| `actions` | `84,966` | `75,369` | `114,911` | 玩家操作指令流（可用于 TP 点击、微操核验） |
| `DOTA_COMBATLOG_DAMAGE` | `40,288` | `28,585` | `37,415` | 伤害明细（用于 TP 落地后首次伤害时间、先手判定） |
| `interval` | `28,400` | `27,920` | `27,140` | 逐秒英雄状态与实时坐标 `(x, y)` |
| `DOTA_COMBATLOG_MODIFIER_ADD` | `16,118` | `10,462` | `10,453` | 状态添加（包含 `modifier_smoke_of_deceit` 开雾、`modifier_teleporting` 等） |
| `DOTA_COMBATLOG_MODIFIER_REMOVE` | `16,102` | `10,432` | `10,397` | 状态结束（精确界定开雾结束/破雾时刻与 TP 完成） |
| `DOTA_COMBATLOG_DEATH` | `4,259` | `4,551` | `3,381` | 击杀与阵亡事件（含 `targetname`/`attackername`/`time`） |
| `pings` | `170` | `218` | `115` | 地图 Signal/Ping 坐标 `(x, y)` |
| `obs` / `obs_left` | `39` / `38` | `37` / `37` | `36` / `36` | 真假眼放置/拔除坐标与真实存活时间 |
| `sen` / `sen_left` | `72` / `66` | `60` / `56` | `66` / `61` | 哨兵守卫放置/拔除坐标与真实存活时间 |
| `CHAT_MESSAGE_SMOKE_ACTIVATED` | `10` | `10` | `7` | 开雾触发系统消息（与 modifier 互补） |

---

## 3. 逐秒位置、坐标系确认与 OpenDota 交叉核对【实测】

### 3.1 `interval` 字段名、采样频率与坐标系公式确认
1. **字段名确认**：每条 `interval` 包含 35 个字段：
   `assists`, `camps_stacked`, `creeps_stacked`, `deaths`, `denies`, `facet_hero_id`, `firstblood_claimed`, `gold`, `hero_damage`, `hero_id`, `kills`, `level`, `lh`, `life_state`, `networth`, `obs_placed`, `observers_placed`, `pred_vict`, `randomed`, `roshans_killed`, `rune_pickups`, `sen_placed`, `slot`, `stage`, `stuns`, `teamfight_participation`, `time`, `tower_damage`, `towers_killed`, `type`, `unit`, `variant`, `x`, `xp`, `y`。
   - 其中位置与阵亡核心字段为 `time`（整数秒）、`slot`（`0..9`）、`unit`（英雄实体名，如 `CDOTA_Unit_Hero_Nyx_Assassin`）、`x`、`y`（连续浮点数）、`life_state`（`0` 存活、`1` 死亡中、`2` 死亡等状态）。
2. **采样频率实测为严格 `1 Hz`（`dt = 1s`）**：
   - `9087090072`（`slot 0..9` 各 `2,840` 条，`t ∈ [-222, 2617]`）：全区间 `dt_histogram_all={"1": 28390}`，`t >= 0` 区间 `dt_histogram_t_ge_0={"1": 26170}`。
   - `9085834639`（`slot 0..9` 各 `2,792` 条，`t ∈ [-223, 2568]`）：全区间 `{"1": 27910}`，`t >= 0` `{"1": 25680}`。
   - `9083213997`（`slot 0..9` 各 `2,714` 条，`t ∈ [-231, 2482]`）：全区间 `{"1": 27130}`，`t >= 0` `{"1": 24820}`。
   - **三场 10 名英雄无一缺失或跳秒**（`dt != 1` 为 `0`）。
3. **坐标系公式实测验证**：
   - 核对 `odota/parser` 源码 `Parse.getPreciseLocation(cell, vec) = (cell * 128.0f + vec) / 128`，三场有坐标记录条数分别为 `27,070` / `26,580` / `25,718`（总计 `79,368` 条；开赛前极早期未刷出实体前不含 `x`/`y`）。
   - 全部 `79,368` 条记录 **100% 满足** `cell ∈ Z, vec ∈ [0, 128)` 与 `(cell * 128 + vec) / 128 == (x, y)`，例如 `x = 177.39014 = (177 * 128 + 49.9379) / 128`。
   - 坐标范围实测落在 Dota 2 标准 Cell 网格 `[64, 192]` 及其泉水边缘（总范围 `x ∈ [61.9976, 194.1316]`、`y ∈ [59.75, 193.25]`）。

### 3.2 与 OpenDota `teamfights[].players[].deaths_pos` 及 `players[].obs_log` 交叉核对【实测】

| 比赛号 | `deaths_pos` 对齐总数 | 原始连续坐标误差均值 / 最大 (cell) | 单次取整完全重合 | **OpenDota 两步舍入完全重合** (`dx=0,dy=0`) | `obs_log` 对齐总数 | **0.1精度完全重合** (`round 0.1`) | 眼位误差均值 / 最大 (cell) |
|---|---|---|---|---|---|---|---|
| `9087090072` | `36 / 36` (8团战) | `0.3815` / `0.6467` | `30 / 36` | **`36 / 36` (100.0%)** | `39 / 39` | **`39 / 39` (100.0%)** | `0.041` / `0.0594` |
| `9085834639` | `42 / 42` (11团战) | `0.4082` / `0.5858` | `41 / 42` | **`42 / 42` (100.0%)** | `37 / 37` | **`37 / 37` (100.0%)** | `0.0379` / `0.0587` |
| `9083213997` | `52 / 52` (11团战) | `0.3745` / `0.6087` | `49 / 52` | **`52 / 52` (100.0%)** | `36 / 36` | **`36 / 36` (100.0%)** | `0.0354` / `0.0643` |
| **合计** | **`130 / 130`** | 最大 `0.6467 < 0.707` | `120 / 130` | **`130 / 130` (100.0%)** | **`112 / 112`** | **`112 / 112` (100.0%)** | 最大 `0.0643 < 0.0707` |

- **原因实测解释**：比对 OpenDota 上游 `CreateParsedDataBlob.java` 与本次实测样本发现，OpenDota 汇总团战 `deaths_pos` 时在 `DOTA_COMBATLOG_DEATH` 时刻先执行 `Math.round(x * 10.0) / 10.0f`（1 位小数舍入），再经 `processTeamfights()` 执行第二次 `Math.round(...)` 取整；按该两步规则验证，**130 例死亡坐标 100% 精确重合（零偏差）**。同样 `obs_log` 为 `Math.round(x * 10.0) / 10.0f`，**112 例假眼坐标 100% 精确重合**，最大欧氏误差 `0.0643` cell 严格落在 1 位小数半网格对角线误差上界 `√(0.05²+0.05²) ≈ 0.0707` cell 内。
- 实测附带验证：若不读 `DOTA_COMBATLOG_DEATH`，而仅用 `interval` 里 `life_state` `0->1` 跳变定位死亡位置，3 场最大误差可达 `5.5489` / `10.6049` / `4.402` cell（因阵亡瞬间在两个 1 秒采样点之间且受击退/位移/泉水复活点影响），故 M1–M3 的“阵亡时刻”应优先基于 `DOTA_COMBATLOG_DEATH`（或其后 0–1s 内 `interval` 状态）。

---

## 4. Valve 录像保留期探针与抓包 SLA【实测】

通过 `tools/replay_lab/check_retention_and_volume.py`（于 `2026-11-15T11:06:05.070216+00:00` 运行，对 Valve CDN URL **仅发 `HTTP HEAD` 请求**，不下载录像体，零昵称/账号/盐值输出）：

### 4.1 `1 / 3 / 7 / 10 / 14 / 21` 天目标及延展边界结果【实测】

| 探测分组 | 比赛号 | 距今 (天) | 同边人数 | OpenDota 状态 | 补丁 | 集群 | `HTTP` 状态 | `Content-Length` | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| `1d (newest sig=0 solo)` | `9087860371` | `2.19` | `1` | `unparsed` | `7.41` | `151` | `N/A` | `-` | `replay_url=None (unparsed on OpenDota)` |
| `1d (closest >=2)` | `9087090072` | `2.82` | `2` | `v22` | `7.41` | `154` | **`200`** | `54,071,426` | 2-stack |
| `3d (next >=2)` | `9085834639` | `3.80` | `3` | `v22` | `7.41` | `152` | **`200`** | `52,132,535` | 3-stack |
| `7d (closest >=2, unparsed)` | `9081263873` | `7.12` | `2` | `unparsed` | `7.41` | `151` | **`200`** | `49,841,531` | 未经 OD 解析但有 URL |
| `7d (parsed >=2)` | `9081933680` | `6.80` | `5` | `v22` | `7.41` | `154` | **`200`** | `43,728,225` | 5-stack |
| `10d (closest >=2)` | `9077212017` | `9.90` | `5` | `v22` | `7.41` | `153` | **`200`** | `39,386,272` | 5-stack |
| `14d (closest >=2, unparsed)` | `9071559155` | `13.94` | `2` | `unparsed` | `7.41` | `153` | **`200`** | `59,321,415` | 未经 OD 解析但有 URL |
| `14d (parsed >=2)` | `9071281304` | `14.08` | `3` | `v22` | `7.41` | `153` | **`200`** | `48,418,271` | 3-stack |
| `21d (closest >=2)` | `9061341080` | `20.91` | `3` | `v22` | `7.41` | `151` | **`200`** | `39,128,379` | 3-stack |
| `Ext 28d (parsed >=2)` | `9051134110` | `27.84` | `2` | `v22` | `7.41` | `152` | **`200`** | `37,378,742` | 延展 |
| `Ext 35d (parsed >=2)` | `9040451712` | `34.76` | `2` | `v22` | `7.41` | `151` | **`200`** | `70,917,422` | 延展 |
| `Ext ~60d (boundary)` | `9001731016` | `59.86` | `n/a` | `v22` | `7.41` | `154` | **`200`** | `33,313,623` | 边界 |
| `Ext ~91.5d (boundary)` | `8947636518` | `91.63` | `n/a` | `v22` | `7.41` | `153` | **`200`** | `56,821,303` | 边界 |
| `Ext ~100.5d (boundary)` | `8932348500` | `100.82` | `n/a` | `unparsed` | `7.41` | `151` | **`200`** | `38,346,024` | **最新仍有效边界** |
| `Ext ~103.5d (boundary)` | `8927541236` | `103.89` | `n/a` | `unparsed` | `7.41` | `151` | **`404`** | `-` | **已清理失效边界** |
| `Ext ~180d (boundary)` | `8817458915` | `179.80` | `n/a` | `unparsed` | `7.41` | `152` | **`404`** | `-` | 已失效 |

### 4.2 实测结论与抓包 SLA 建议
- **Valve SEA CDN 实际保留窗（集群 `151–154`）**：实测 `2.82d` 至 `100.82d` 连续返回 `HTTP 200`，从 `103.89d` 起返回 `HTTP 404`（当前保留窗约 **100.8–103.9 天**）。13 个 `HTTP 200` 样本 `.dem.bz2` 大小实测为最小 `31.77 MiB` / 中位 `46.18 MiB` / 均值 `45.69 MiB` / 最大 `67.63 MiB`。
- **真正的短板不是 CDN 404，而是 OpenDota 的 `replay_url=None` 缺失率**：过去 28 天 77 场 `>=2` 车队比赛中高达 `34 / 77`（`44.2%`）在 OpenDota 上仍为 `unparsed`，且新近普通匹配（如 `2.19d` 的 `9087860371`）`/api/matches/{id}` 直接返回 `replay_url=None`。
- **建议的赛后抓包 SLA**：
  - **主抓取**：复用 `postgame_notify` 赛后检测，在比赛结束后 **`<= 2 小时`** 内向 OpenDota 触发一次 `POST /api/request/{match_id}` 以获取 `replay_salt` / `replay_url`，并在 **24 小时内带退避重试**；一拿到 `replay_url` 立即下载解析。
  - **历史补抓安全上限**：设置为 **`<= 7 天`**（即使未来 Valve 将 SEA 集群缩回常见的 7–14 天保留策略，仍保留足够缓冲空间；对于过往 100 天内未失效的历史车队场次也可做一次性存量补抓）。

---

## 5. GitHub Actions `ubuntu-latest` 实测（匿名日志）

- **真实执行链接**：[`43707314979`](https://github.com/richardlau898-sys/dota-5stack-ledger/actions/runs/43707314979)（工作流 `.github/workflows/m0_replay_bench.yml`，分支 `feat/m0-replay-feasibility`，提交 `e2ff292`）。
- **匿名保密校验**：已逐行扫描 Actions 全日志，`0` 比赛号、`0` 玩家昵称、`0` Steam/Account ID、`0` Valve URL/盐值、`0` 原始 JSONL 行、`0` Actions Artifact；跑完自动清理 `/tmp/m0_gha` 与 `/tmp/m0_gha_parser`。

| 实测维度 | GitHub Actions (`ubuntu-latest`) 实测值 |
|---|---|
| 宿主机规格 | `Linux-7.0.0-1019-azure-x86_64-with-glibc2.43`，`4` vCPU (`AMD EPYC 9V74 80-Core Processor`)，`MemTotal: 16366640 kB`（`15.61 GiB`），`MemAvailable: 15106332 kB` |
| 构建与运行工具 | Temurin `21.0.13+9`，Maven `3.9.15`，`zstd v1.5.7`，`odota/parser` `67945be040de92d0ba9cdedc77434886d4f736be` |
| 动态命中场次（匿名元数据） | `patch=60`，`duration_sec=2616`，`squad_roster_count=2`，`head_status=200` |
| 各步耗时 | 下载 `61.398s`；`zstd -d -f` 解压 `0.133s`；**`ParseCli` 解析 `4.972s`**（`0:04.97` elapsed，`10.56s` user，`0.58s` sys，`224%` CPU）；`gzip -9` 全量 `0.866s`；`compact_01` 压缩 `0.122s`；**整条 Job 含拉取构建总计 `1m51s`** |
| **内存峰值 (`/usr/bin/time -v`)** | **`Maximum resident set size (kbytes): 649912`**（约 `634.68 MiB`，仅占 Runner 总内存约 `4.0%`）；Major page faults: `2`，Swaps: `0` |
| 产出体积 | `dem_bz2`: `54,071,426 B`；`dem`: `91,934,749 B`；`jsonl`: `52,966,593 B`（`210,452` 行）；`jsonl_gz`: `2,156,594 B`；`compact_01_json_gz`: `145,622 B`；`compact_int_json_gz`: `106,784 B` |

**环境可行性结论**：免费公共 GitHub Actions `ubuntu-latest` 足以胜任 `odota/parser` 录像解析，无需升级付费大内存 Runner。

---

## 6. 近 4 周比赛量（实测）、月度存储（预估）与 Supabase 配额检查（做不到）

### 6.1 近 4 周（28 天）历史场次统计【实测】

来源：`python3 tools/replay_lab/check_retention_and_volume.py`（于 `2026-11-15T11:06:05Z` 对 `roster.json` 全部 11 个账号去重汇总）：

| 时间窗口 | Default 总去重场次 | Default 车队 (`>=2`) | Default 已解析 (`>=2`) | Default `5-Roster` / `party_size=5` | `significant=0` 总去重 (含加速/娱乐) | `significant=0` 车队 (`>=2`) |
|---|---|---|---|---|---|---|
| `<= 3.00d` | `1` | `1` | `1` | `0` / `0` | `2` | `1` |
| `Week -1 (0-7d]` | `15` | `13` | `6` | `3` / `4` | `18` | `15` |
| `Week -2 (7-14d]` | `57` | `27` | `13` | `7` / `8` | `62` | `30` |
| `Week -3 (14-21d]` | `46` | `21` | `14` | `4` / `4` | `49` | `22` |
| `Week -4 (21-28d]` | `67` | `16` | `10` | `2` / `2` | `68` | `17` |
| **过去 28 天合计** | **`185`** | **`77`** | **`43`** | **`16` / `18`** | **`197`** | **`84`** |
| 过去 35 天合计 | `230` | `99` | `57` | `23` / `26` | `248` | `106` |

> 过去 28 天 Default 车队栈规模明细【实测】：`2-roster = 29` 场、`3-roster = 22` 场、`4-roster = 10` 场、`5-roster = 16` 场（`1-roster` 单排或仅 1 名花名册成员出场 = `108` 场）。

### 6.2 月度存储增长【预估】（均附明确计算公式）

> **计算公式**：`月场数 = (28 天总场次 / 4 周) × 4.33 周/月`；`月度增量 = 月场数 × 第 2.2 节 3 场实测均值`（`compact_01_json_gz = 139,579 B ≈ 136.31 KiB`；全量 `jsonl_gz = 1,970,482 B ≈ 1.88 MiB`；原始 `.dem.bz2 = 53,506,669 B ≈ 51.03 MiB`）。

| 场景口径（【预估】） | 周均场数 | 预估月场数 (`×4.33`) | 仅存 1Hz `timeline.json.gz`（推荐） | 额外保留全量 `jsonl.gz` | 若保留原始 `.dem.bz2`（反面参考） |
|---|---|---|---|---|---|
| **基准：Default 车队 (`>=2`) `77` 场/28天** | `19.25` 场/周 | `83.35` 场/月 | **`11.10 MiB/月`**（`133.14 MiB/年`） | `156.64 MiB/月`（`1.84 GiB/年`） | `4.15 GiB/月`（`49.84 GiB/年`） |
| **全模式：All-Modes 车队 (`>=2`) `84` 场/28天** | `21.00` 场/周 | `90.93` 场/月 | **`12.10 MiB/月`**（`145.25 MiB/年`） | `170.88 MiB/月`（`2.00 GiB/年`） | `4.53 GiB/月`（`54.37 GiB/年`） |
| 上限：花名册全量含单排 `197` 场/28天 | `49.25` 场/周 | `213.25` 场/月 | `28.39 MiB/月`（`340.64 MiB/年`） | `400.74 MiB/月`（`4.70 GiB/年`） | `10.63 GiB/月`（`127.52 GiB/年`） |

*(注：若在 `timeline.json.gz` 中进一步同时保存精简眼位/阵亡/开雾/TP 摘要事件，其体积预计仍仅为 `jsonl.gz` 的零头，将在 M1 Schema 设计里定型并再次实测体积。)*

### 6.3 Supabase 当前套餐实际额度核查：**做不到**

> **状态**：**`做不到`** —— 当前运行环境无法观测、获取或截图 `dota-5stack-ledger` 生产 Supabase 项目的当前套餐及 Storage 已用/剩余额度，严格按规则拒绝猜测 Free/Pro 或编造配额数字。精确阻塞原因如下：
> 1. **浏览器后台未登录**：访问 `https://supabase.com/dashboard` 会被重定向至 `https://supabase.com/dashboard/sign-in?returnTo=%2Forg`，无法截取 Dashboard 的 Billing / Storage Quota 页面。
> 2. **本地仓库与环境无生产 Supabase 凭据**：本地工作区仅存在 `.env.local`（不含任何 `SUPABASE_URL` / `SUPABASE_*` 键值），当前进程环境变量亦无 `SUPABASE_*`，`cloud_store.py` 仅在运行期读取外部注入的 env/secrets，且本机未安装 `vercel` CLI（`command not found: vercel`），无法反查 Vercel 生产环境变量中的项目 ref。
> 3. **现有 `supabase_mcp` 会话未绑定生产项目**：当前连接的 MCP 组织 `qievxrnxhflosdwjleah`（`plan: pro`）下仅可见项目 `keen` 与 `mp4`，两者 `public` schema 中均不存在本项目的 `dota_match_reports`、`match_players` 或 `dota_llm_tasks` 表。

---

## 7. 交付清单与 Richard 检查点（D11–D13 决策）

### 7.1 M0 交付物清单
1. [`docs/project_replay_lab.md`](project_replay_lab.md)：从需求文档原样复制归档（`diff -u` 零差异）。
2. [`docs/m0_replay_feasibility.md`](m0_replay_feasibility.md)：本可行性实测报告。
3. [`tools/replay_lab/ParseCli.java`](../tools/replay_lab/ParseCli.java)：调用 `opendota.Parse` 的轻量 CLI 包装器（27 行）。
4. [`tools/replay_lab/run_local_m0.py`](../tools/replay_lab/run_local_m0.py)：3 场本地全流程基准与 OpenDota 坐标交叉核对脚本。
5. [`tools/replay_lab/check_retention_and_volume.py`](../tools/replay_lab/check_retention_and_volume.py)：Valve HTTP `HEAD` 保留期探针与 28 天场次统计脚本。
6. [`tools/replay_lab/gha_m0_bench.py`](../tools/replay_lab/gha_m0_bench.py) & [`.github/workflows/m0_replay_bench.yml`](../.github/workflows/m0_replay_bench.yml)：公开仓库匿名 GitHub Actions 基准脚本与工作流。
7. [`tools/replay_lab/sample_9083213997_excerpt.jsonl`](../tools/replay_lab/sample_9083213997_excerpt.jsonl)：**来自比赛号 `9083213997`（`patch=60`，5-stack）的真实未修改 JSONL 样本**，共 **`181` 行**（`68,246` 字节，满足 `<= 200` 行），包含：`interval` (`80`)、`pings` (`15`)、`obs` (`15`)、`DOTA_COMBATLOG_DEATH` (`15`)、`obs_left` (`15`)、`DOTA_COMBATLOG_ITEM` (`10`)、`DOTA_COMBATLOG_DAMAGE` (`10`)、`DOTA_COMBATLOG_MODIFIER_ADD` (`8`，含开雾与 TP)、`DOTA_COMBATLOG_MODIFIER_REMOVE` (`7`)、`DOTA_COMBATLOG_ABILITY` (`6`)；已校验 `0` 条 `epilogue`、`0` 条 `chat`、`0` 玩家昵称、`0` Steam/Account ID。

### 7.2 等待 Richard 在 M0 检查点拍板的问题与建议
- **待补充项**：请在 Supabase 后台确认生产项目实际所在组织/套餐（Free 还是 Pro）与 Storage 当前配额及已用空间，以核对第 6.2 节的 `~11.1 MiB/月`（纯 1Hz 精简时间轴）vs `~156.6 MiB/月`（含全量 `jsonl.gz`）是否均远在免费额度内。
- **D11（解析结果保存策略）**：**建议长期保存精简解析结果（`timeline.json.gz`，实测 ~`136 KiB/场`，预估 `~11.1–12.1 MiB/月`）；绝不长期保存原始录像 `.dem.bz2`（预估 `~4.15–4.53 GiB/月`）**。至于全量 `jsonl.gz`（~`1.88 MiB/场`），建议仅在开发 M3 期间临时留存或从单场原始格式按需抽取结构化事件后丢弃。
- **D12（仓库是否继续公开）**：**建议继续保持公开**。实测 GitHub Actions `ubuntu-latest` 全流程仅 `1m51s`、内存峰值 `634.68 MiB`，公开仓库可免费不限时长运行且已有严格匿名日志约束（严禁日志打印比赛号、玩家信息、盐值 URL 或 Actions artifacts）。
- **D13（是否继续 M1–M3）**：**建议批准继续 M1–M3**。全部核心技术前提（Zstd 解压适配、`odota/parser` 最新补丁兼容性、`1Hz` 连续坐标、与 `deaths_pos` 130/130 及 `obs_log` 112/112 的 100% 对齐、百天保留窗与低存储成本）已通过 M0 实测验证，唯一前置依赖仅是在 M1 设计 PR 前确认生产 Supabase Storage 配额并获得你的 M1 设计批准。

---

## 8. 附录：完整原始命令输出（供零遗漏审计）

### 附录 1：本地环境、工具链与样本文件校验输出

```text
$ uname -ms && sw_vers && sysctl -n machdep.cpu.brand_string hw.ncpu hw.memsize && /tmp/m0_replay_work/toolchain/jdk-21.0.13+9/Contents/Home/bin/java -version 2>&1 && JAVA_HOME=/tmp/m0_replay_work/toolchain/jdk-21.0.13+9/Contents/Home /tmp/m0_replay_work/toolchain/apache-maven-3.9.9/bin/mvn -version && git -C /tmp/m0_replay_work/odota-parser rev-parse HEAD && wc -c /tmp/m0_replay_work/odota-parser/target/stats-0.1.0.jar && cd /tmp/wt_m0_replay && wc -l -c tools/replay_lab/sample_9083213997_excerpt.jsonl && python3 -c "import collections,json; c=collections.Counter(json.loads(l)['type'] for l in open('tools/replay_lab/sample_9083213997_excerpt.jsonl')); print(dict(c.most_common()))"
Darwin arm64
ProductName:		macOS
ProductVersion:		26.6.2
BuildVersion:		25G83
Apple M5 Pro
18
25769803776
openjdk version "21.0.13" 2026-10-20 LTS
OpenJDK Runtime Environment Temurin-21.0.13+9 (build 21.0.13+9-LTS)
OpenJDK 64-Bit Server VM Temurin-21.0.13+9 (build 21.0.13+9-LTS, mixed mode, sharing)
Apache Maven 3.9.9 (8e8579a9e76f7d015ee5ec7bfcdc97d260186937)
Maven home: /tmp/m0_replay_work/toolchain/apache-maven-3.9.9
Java version: 21.0.13, vendor: Eclipse Adoptium, runtime: /private/tmp/m0_replay_work/toolchain/jdk-21.0.13+9/Contents/Home
Default locale: en_SG, platform encoding: UTF-8
OS name: "mac os x", version: "26.6.2", arch: "aarch64", family: "mac"
67945be040de92d0ba9cdedc77434886d4f736be
 29090157 /tmp/m0_replay_work/odota-parser/target/stats-0.1.0.jar
     181   68246 tools/replay_lab/sample_9083213997_excerpt.jsonl
{'interval': 80, 'pings': 15, 'obs': 15, 'DOTA_COMBATLOG_DEATH': 15, 'obs_left': 15, 'DOTA_COMBATLOG_ITEM': 10, 'DOTA_COMBATLOG_DAMAGE': 10, 'DOTA_COMBATLOG_MODIFIER_ADD': 8, 'DOTA_COMBATLOG_MODIFIER_REMOVE': 7, 'DOTA_COMBATLOG_ABILITY': 6}
```

### 附录 2：本地 3 场基准与交叉核对完整输出（`python3 -u tools/replay_lab/run_local_m0.py --force-download`）

<details>
<summary>点击展开完整原始输出（共 1572 行，含 3 场全量耗时、字节大小、全事件计数、`interval` 采样验证及 `deaths_pos` / `obs_log` 交叉核对结果）</summary>

```text
UTC_RUN_AT=2026-11-15T11:04:46.474478+00:00
ODOTA_PARSER_COMMIT=67945be040de92d0ba9cdedc77434886d4f736be
JAVA_VERSION=openjdk version "21.0.13" 2026-10-20 LTS | OpenJDK Runtime Environment Temurin-21.0.13+9 (build 21.0.13+9-LTS) | OpenJDK 64-Bit Server VM Temurin-21.0.13+9 (build 21.0.13+9-LTS, mixed mode, sharing)
BZIP2_VERSION=bzip2, a block-sorting file compressor.  Version 1.0.8, 13-Jul-2019.
ZSTD_VERSION=*** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***
{
  "utc_run_at": "2026-11-15T11:05:28.028776+00:00",
  "odota_parser_commit": "67945be040de92d0ba9cdedc77434886d4f736be",
  "matches": [
    {
      "match_id": 9087090072,
      "patch": 60,
      "duration_sec": 2616,
      "start_time_utc": "2026-11-12T15:30:07+00:00",
      "replay_url_redacted": "http://replay154.valve.net/570/9087090072_<SALT_REDACTED>.dem.bz2",
      "download_sec": 23.36,
      "detected_payload_compression": "zstd",
      "decompress_tool": "zstd -d -f",
      "file_dem_bz2": "/tmp/m0_replay_work/replays/9087090072.dem.bz2: Zstandard compressed data (v0.8+), Dictionary ID: None",
      "file_dem": "/tmp/m0_replay_work/replays/9087090072.dem: data",
      "dem_magic_hex": "504244454d533200",
      "decompress_sec": 0.09,
      "parse_wall_sec": 3.207,
      "parse_time_l": {
        "raw_lines": [
          "SLF4J(W): No SLF4J providers were found.",
          "SLF4J(W): Defaulting to no-operation (NOP) logger implementation",
          "SLF4J(W): See https://www.slf4j.org/codes.html#noProviders for further details.",
          "        3.20 real         4.41 user         0.39 sys",
          "           552943616  maximum resident set size",
          "                   0  average shared memory size",
          "                   0  average unshared data size",
          "                   0  average unshared stack size",
          "               48637  page reclaims",
          "                1791  page faults",
          "                   0  swaps",
          "                   0  block input operations",
          "                   0  block output operations",
          "                   0  messages sent",
          "                   0  messages received",
          "               10851  signals received",
          "                 453  voluntary context switches",
          "               30546  involuntary context switches",
          "         57070112250  instructions retired",
          "         20183550982  cycles elapsed",
          "           552977656  peak memory footprint"
        ],
        "real_sec": 3.2,
        "user_sec": 4.41,
        "sys_sec": 0.39,
        "max_rss_bytes": 552943616,
        "max_rss_mib": 527.33,
        "peak_footprint_bytes": 552977656,
        "peak_footprint_mib": 527.36
      },
      "gzip_jsonl_sec": 0.37,
      "compact_01_gzip_sec": 0.057,
      "sizes_bytes": {
        "dem_bz2": 54071426,
        "dem": 91934749,
        "jsonl": 52966593,
        "jsonl_gz": 2156386,
        "compact_01_json_raw": 526678,
        "compact_01_json_gz": 146572,
        "compact_int_json_raw": 422129,
        "compact_int_json_gz": 107641
      },
      "jsonl_total_lines": 210452,
      "event_type_counts": {
        "actions": 84966,
        "DOTA_COMBATLOG_DAMAGE": 40288,
        "interval": 28400,
        "DOTA_COMBATLOG_MODIFIER_ADD": 16118,
        "DOTA_COMBATLOG_MODIFIER_REMOVE": 16102,
        "DOTA_COMBATLOG_ABILITY": 4449,
        "DOTA_COMBATLOG_XP": 4371,
        "DOTA_COMBATLOG_HEAL": 4367,
        "DOTA_COMBATLOG_DEATH": 4259,
        "DOTA_COMBATLOG_GOLD": 3262,
        "DOTA_COMBATLOG_ITEM": 1375,
        "DOTA_COMBATLOG_PURCHASE": 570,
        "DOTA_ABILITY_LEVEL": 424,
        "DOTA_COMBATLOG_PLAYERSTATS": 317,
        "pings": 170,
        "assist_tick": 134,
        "sen": 72,
        "neutral_item_history": 70,
        "CHAT_MESSAGE_HERO_KILL": 69,
        "death_tick": 69,
        "sen_left": 66,
        "CHAT_MESSAGE_ITEM_PURCHASE": 60,
        "CHAT_MESSAGE_RUNE_PICKUP": 53,
        "STARTING_ITEM": 53,
        "chatwheel": 52,
        "obs": 39,
        "obs_left": 38,
        "CHAT_MESSAGE_STREAK_KILL": 26,
        "CHAT_MESSAGE_SENTRY_WARD_KILLED": 22,
        "DOTA_COMBATLOG_TEAM_BUILDING_KILL": 19,
        "DOTA_COMBATLOG_KILLSTREAK": 18,
        "CHAT_MESSAGE_HERO_BANNED": 16,
        "CHAT_MESSAGE_OBSERVER_WARD_KILLED": 13,
        "CHAT_MESSAGE_TOWER_KILL": 12,
        "DOTA_COMBATLOG_GAME_STATE": 10,
        "player_slot": 10,
        "CHAT_MESSAGE_SMOKE_ACTIVATED": 10,
        "CHAT_MESSAGE_DISCONNECT": 10,
        "CHAT_MESSAGE_RUNE_BOTTLE": 9,
        "DOTA_COMBATLOG_MULTIKILL": 9,
        "CHAT_MESSAGE_SCAN_USED": 7,
        "chat": 5,
        "CHAT_MESSAGE_PAUSE_COUNTDOWN": 4,
        "CHAT_MESSAGE_GLYPH_USED": 4,
        "DOTA_COMBATLOG_ABILITY_TRIGGER": 4,
        "CHAT_MESSAGE_BARRACKS_KILL": 4,
        "CHAT_MESSAGE_UNPAUSE_COUNTDOWN": 3,
        "CHAT_MESSAGE_INTHEBAG": 2,
        "CHAT_MESSAGE_BUYBACK": 2,
        "DOTA_COMBATLOG_BUYBACK": 2,
        "draft_start": 1,
        "CHAT_MESSAGE_REPORT_REMINDER": 1,
        "CHAT_MESSAGE_INFORMATIONAL": 1,
        "CHAT_MESSAGE_FIRSTBLOOD": 1,
        "DOTA_COMBATLOG_FIRST_BLOOD": 1,
        "CHAT_MESSAGE_RUNE_DENY": 1,
        "CHAT_MESSAGE_PAUSED": 1,
        "CHAT_MESSAGE_UNPAUSED": 1,
        "game_paused": 1,
        "CHAT_MESSAGE_TOWER_DENY": 1,
        "CHAT_MESSAGE_COURIER_LOST": 1,
        "CHAT_MESSAGE_COURIER_RESPAWNED": 1,
        "CHAT_MESSAGE_ROSHAN_KILL": 1,
        "CHAT_MESSAGE_AEGIS": 1,
        "CHAT_MESSAGE_MINIBOSS_KILL": 1,
        "cosmetics": 1,
        "dotaplus": 1,
        "epilogue": 1
      },
      "interval_analysis": {
        "all_keys_sorted": [
          "assists",
          "camps_stacked",
          "creeps_stacked",
          "deaths",
          "denies",
          "facet_hero_id",
          "firstblood_claimed",
          "gold",
          "hero_damage",
          "hero_id",
          "kills",
          "level",
          "lh",
          "life_state",
          "networth",
          "obs_placed",
          "observers_placed",
          "pred_vict",
          "randomed",
          "roshans_killed",
          "rune_pickups",
          "sen_placed",
          "slot",
          "stage",
          "stuns",
          "teamfight_participation",
          "time",
          "tower_damage",
          "towers_killed",
          "type",
          "unit",
          "variant",
          "x",
          "xp",
          "y"
        ],
        "sample_interval_entry": {
          "time": 0,
          "type": "interval",
          "unit": "CDOTA_Unit_Hero_Juggernaut",
          "slot": 0,
          "gold": 0,
          "tower_damage": 0,
          "lh": 0,
          "xp": 0,
          "x": 133.1792,
          "y": 90.90381,
          "stuns": 0.0,
          "hero_id": 8,
          "variant": 0,
          "facet_hero_id": 8,
          "life_state": 0,
          "level": 1,
          "kills": 0,
          "deaths": 0,
          "assists": 0,
          "denies": 0,
          "obs_placed": 0,
          "sen_placed": 0,
          "creeps_stacked": 0,
          "camps_stacked": 0,
          "rune_pickups": 0,
          "randomed": false,
          "pred_vict": false,
          "firstblood_claimed": 0,
          "teamfight_participation": 0.0,
          "towers_killed": 0,
          "roshans_killed": 0,
          "observers_placed": 0,
          "networth": 598,
          "hero_damage": 0,
          "stage": 4
        },
        "dt_histogram_all": {
          "1": 28390
        },
        "dt_histogram_t_ge_0": {
          "1": 26170
        },
        "slots_summary": {
          "0": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "1": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "2": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "3": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "4": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "5": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "6": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "7": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "8": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          },
          "9": {
            "count_all": 2840,
            "count_t_ge_0": 2618,
            "min_t": -222,
            "max_t": 2617
          }
        },
        "coord_count": 27070,
        "min_x": 61.9976,
        "max_x": 194.0098,
        "min_y": 62.7808,
        "max_y": 192.0027,
        "in_64_192_count": 26878,
        "cell_vec_formula_valid_count": 27070,
        "cell_vec_examples": [
          {
            "time": 60,
            "slot": 0,
            "x": 177.39014,
            "y": 96.58374,
            "cellX": 177,
            "vecX": 49.9379,
            "cellY": 96,
            "vecY": 74.7187,
            "reconstructed_x": 177.39014,
            "reconstructed_y": 96.58374
          },
          {
            "time": 60,
            "slot": 1,
            "x": 169.18384,
            "y": 95.16235,
            "cellX": 169,
            "vecX": 23.5315,
            "cellY": 95,
            "vecY": 20.7808,
            "reconstructed_x": 169.18384,
            "reconstructed_y": 95.16235
          },
          {
            "time": 60,
            "slot": 2,
            "x": 78.805176,
            "y": 167.40576,
            "cellX": 78,
            "vecX": 103.0625,
            "cellY": 167,
            "vecY": 51.9373,
            "reconstructed_x": 78.805176,
            "reconstructed_y": 167.40576
          }
        ]
      },
      "crosscheck_deaths_pos": {
        "od_teamfights_count": 8,
        "od_total_deaths_pos_entries": 36,
        "matched_via_combatlog_death": 36,
        "exact_java_round_matches": 30,
        "exact_od_two_step_round_matches": 36,
        "within_1_cell": 36,
        "within_2_cells": 36,
        "raw_euclid_min": 0.0338,
        "raw_euclid_mean": 0.3815,
        "raw_euclid_max": 0.6467,
        "round_max_dx": 1,
        "round_max_dy": 1,
        "matched_via_lifestate": 36,
        "lifestate_euclid_mean": 0.8844,
        "lifestate_euclid_max": 5.5489,
        "samples": [
          {
            "tf_idx": 0,
            "slot": 3,
            "parser_xy": [
              111.927,
              117.521
            ],
            "parser_round_xy": [
              112,
              118
            ],
            "od_deaths_pos_xy": [
              112,
              118
            ],
            "euclid_err_raw": 0.484,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 4,
            "parser_xy": [
              121.051,
              124.607
            ],
            "parser_round_xy": [
              121,
              125
            ],
            "od_deaths_pos_xy": [
              121,
              125
            ],
            "euclid_err_raw": 0.396,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 8,
            "parser_xy": [
              128.06,
              126.385
            ],
            "parser_round_xy": [
              128,
              126
            ],
            "od_deaths_pos_xy": [
              128,
              126
            ],
            "euclid_err_raw": 0.39,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 9,
            "parser_xy": [
              114.469,
              127.183
            ],
            "parser_round_xy": [
              114,
              127
            ],
            "od_deaths_pos_xy": [
              115,
              127
            ],
            "euclid_err_raw": 0.562,
            "round_dx_dy": [
              1,
              0
            ]
          },
          {
            "tf_idx": 1,
            "slot": 7,
            "parser_xy": [
              92.372,
              131.37
            ],
            "parser_round_xy": [
              92,
              131
            ],
            "od_deaths_pos_xy": [
              92,
              131
            ],
            "euclid_err_raw": 0.524,
            "round_dx_dy": [
              0,
              0
            ]
          }
        ]
      },
      "crosscheck_obs_log": {
        "od_obs_log_count": 39,
        "parser_obs_count": 39,
        "matched_count": 39,
        "exact_01_round_matches": 39,
        "dx_max": 0.0495,
        "dy_max": 0.0488,
        "euclid_mean": 0.041,
        "euclid_max": 0.0594,
        "samples": [
          {
            "time": 21,
            "slot": 1,
            "parser_xy": [
              173.276,
              102.953
            ],
            "od_obs_log_xy": [
              173.3,
              103.0
            ],
            "euclid_err": 0.0526
          },
          {
            "time": 338,
            "slot": 1,
            "parser_xy": [
              181.337,
              95.332
            ],
            "od_obs_log_xy": [
              181.3,
              95.3
            ],
            "euclid_err": 0.0485
          },
          {
            "time": 728,
            "slot": 1,
            "parser_xy": [
              180.557,
              97.172
            ],
            "od_obs_log_xy": [
              180.6,
              97.2
            ],
            "euclid_err": 0.0511
          },
          {
            "time": 884,
            "slot": 1,
            "parser_xy": [
              119.527,
              138.804
            ],
            "od_obs_log_xy": [
              119.5,
              138.8
            ],
            "euclid_err": 0.027
          },
          {
            "time": 929,
            "slot": 1,
            "parser_xy": [
              141.208,
              102.28
            ],
            "od_obs_log_xy": [
              141.2,
              102.3
            ],
            "euclid_err": 0.0211
          }
        ]
      }
    },
    {
      "match_id": 9085834639,
      "patch": 60,
      "duration_sec": 2567,
      "start_time_utc": "2026-11-11T15:56:51+00:00",
      "replay_url_redacted": "http://replay152.valve.net/570/9085834639_<SALT_REDACTED>.dem.bz2",
      "download_sec": 2.272,
      "detected_payload_compression": "zstd",
      "decompress_tool": "zstd -d -f",
      "file_dem_bz2": "/tmp/m0_replay_work/replays/9085834639.dem.bz2: Zstandard compressed data (v0.8+), Dictionary ID: None",
      "file_dem": "/tmp/m0_replay_work/replays/9085834639.dem: data",
      "dem_magic_hex": "504244454d533200",
      "decompress_sec": 0.117,
      "parse_wall_sec": 2.768,
      "parse_time_l": {
        "raw_lines": [
          "SLF4J(W): No SLF4J providers were found.",
          "SLF4J(W): Defaulting to no-operation (NOP) logger implementation",
          "SLF4J(W): See https://www.slf4j.org/codes.html#noProviders for further details.",
          "        2.76 real         3.94 user         0.30 sys",
          "           554729472  maximum resident set size",
          "                   0  average shared memory size",
          "                   0  average unshared data size",
          "                   0  average unshared stack size",
          "               46609  page reclaims",
          "                   5  page faults",
          "                   0  swaps",
          "                   0  block input operations",
          "                   0  block output operations",
          "                   0  messages sent",
          "                   0  messages received",
          "               10713  signals received",
          "                 215  voluntary context switches",
          "               16939  involuntary context switches",
          "         55595528560  instructions retired",
          "         17709927421  cycles elapsed",
          "           542131424  peak memory footprint"
        ],
        "real_sec": 2.76,
        "user_sec": 3.94,
        "sys_sec": 0.3,
        "max_rss_bytes": 554729472,
        "max_rss_mib": 529.03,
        "peak_footprint_bytes": 542131424,
        "peak_footprint_mib": 517.02
      },
      "gzip_jsonl_sec": 0.344,
      "compact_01_gzip_sec": 0.054,
      "sizes_bytes": {
        "dem_bz2": 52132535,
        "dem": 88942221,
        "jsonl": 43807456,
        "jsonl_gz": 1811562,
        "compact_01_json_raw": 517093,
        "compact_01_json_gz": 139414,
        "compact_int_json_raw": 414549,
        "compact_int_json_gz": 101970
      },
      "jsonl_total_lines": 175988,
      "event_type_counts": {
        "actions": 75369,
        "DOTA_COMBATLOG_DAMAGE": 28585,
        "interval": 27920,
        "DOTA_COMBATLOG_MODIFIER_ADD": 10462,
        "DOTA_COMBATLOG_MODIFIER_REMOVE": 10432,
        "DOTA_COMBATLOG_HEAL": 4857,
        "DOTA_COMBATLOG_XP": 4745,
        "DOTA_COMBATLOG_DEATH": 4551,
        "DOTA_COMBATLOG_GOLD": 3104,
        "DOTA_COMBATLOG_ABILITY": 2011,
        "DOTA_COMBATLOG_ITEM": 1336,
        "DOTA_COMBATLOG_PURCHASE": 570,
        "DOTA_ABILITY_LEVEL": 429,
        "DOTA_COMBATLOG_PLAYERSTATS": 313,
        "pings": 218,
        "assist_tick": 138,
        "chatwheel": 91,
        "neutral_item_history": 70,
        "CHAT_MESSAGE_HERO_KILL": 65,
        "death_tick": 65,
        "CHAT_MESSAGE_ITEM_PURCHASE": 64,
        "sen": 60,
        "sen_left": 56,
        "CHAT_MESSAGE_RUNE_PICKUP": 53,
        "STARTING_ITEM": 51,
        "obs": 37,
        "obs_left": 37,
        "CHAT_MESSAGE_STREAK_KILL": 30,
        "DOTA_COMBATLOG_TEAM_BUILDING_KILL": 29,
        "CHAT_MESSAGE_RUNE_BOTTLE": 22,
        "DOTA_COMBATLOG_KILLSTREAK": 22,
        "chat": 21,
        "CHAT_MESSAGE_SENTRY_WARD_KILLED": 17,
        "CHAT_MESSAGE_HERO_BANNED": 16,
        "CHAT_MESSAGE_TOWER_KILL": 15,
        "CHAT_MESSAGE_SCAN_USED": 14,
        "CHAT_MESSAGE_OBSERVER_WARD_KILLED": 12,
        "DOTA_COMBATLOG_GAME_STATE": 10,
        "player_slot": 10,
        "CHAT_MESSAGE_GLYPH_USED": 10,
        "CHAT_MESSAGE_SMOKE_ACTIVATED": 10,
        "DOTA_COMBATLOG_MULTIKILL": 10,
        "CHAT_MESSAGE_DISCONNECT": 10,
        "DOTA_COMBATLOG_ABILITY_TRIGGER": 7,
        "CHAT_MESSAGE_BARRACKS_KILL": 6,
        "CHAT_MESSAGE_BUYBACK": 4,
        "DOTA_COMBATLOG_BUYBACK": 4,
        "CHAT_MESSAGE_INTHEBAG": 3,
        "CHAT_MESSAGE_COURIER_LOST": 3,
        "CHAT_MESSAGE_COURIER_RESPAWNED": 3,
        "draft_start": 1,
        "CHAT_MESSAGE_REPORT_REMINDER": 1,
        "CHAT_MESSAGE_INFORMATIONAL": 1,
        "CHAT_MESSAGE_FIRSTBLOOD": 1,
        "DOTA_COMBATLOG_FIRST_BLOOD": 1,
        "CHAT_MESSAGE_ROSHAN_KILL": 1,
        "CHAT_MESSAGE_AEGIS": 1,
        "CHAT_MESSAGE_SUPER_CREEPS": 1,
        "cosmetics": 1,
        "dotaplus": 1,
        "epilogue": 1
      },
      "interval_analysis": {
        "all_keys_sorted": [
          "assists",
          "camps_stacked",
          "creeps_stacked",
          "deaths",
          "denies",
          "facet_hero_id",
          "firstblood_claimed",
          "gold",
          "hero_damage",
          "hero_id",
          "kills",
          "level",
          "lh",
          "life_state",
          "networth",
          "obs_placed",
          "observers_placed",
          "pred_vict",
          "randomed",
          "roshans_killed",
          "rune_pickups",
          "sen_placed",
          "slot",
          "stage",
          "stuns",
          "teamfight_participation",
          "time",
          "tower_damage",
          "towers_killed",
          "type",
          "unit",
          "variant",
          "x",
          "xp",
          "y"
        ],
        "sample_interval_entry": {
          "time": 0,
          "type": "interval",
          "unit": "CDOTA_Unit_Hero_SkeletonKing",
          "slot": 0,
          "gold": 0,
          "tower_damage": 0,
          "lh": 0,
          "xp": 0,
          "x": 117.86841,
          "y": 162.14209,
          "stuns": 0.0,
          "hero_id": 42,
          "variant": 0,
          "facet_hero_id": 42,
          "life_state": 0,
          "level": 1,
          "kills": 0,
          "deaths": 0,
          "assists": 0,
          "denies": 0,
          "obs_placed": 0,
          "sen_placed": 0,
          "creeps_stacked": 0,
          "camps_stacked": 0,
          "rune_pickups": 0,
          "randomed": false,
          "pred_vict": true,
          "firstblood_claimed": 0,
          "teamfight_participation": 0.0,
          "towers_killed": 0,
          "roshans_killed": 0,
          "observers_placed": 0,
          "networth": 592,
          "hero_damage": 0,
          "stage": 4
        },
        "dt_histogram_all": {
          "1": 27910
        },
        "dt_histogram_t_ge_0": {
          "1": 25680
        },
        "slots_summary": {
          "0": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "1": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "2": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "3": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "4": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "5": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "6": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "7": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "8": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          },
          "9": {
            "count_all": 2792,
            "count_t_ge_0": 2569,
            "min_t": -223,
            "max_t": 2568
          }
        },
        "coord_count": 26580,
        "min_x": 62.25,
        "max_x": 194.1316,
        "min_y": 59.75,
        "max_y": 193.25,
        "in_64_192_count": 26302,
        "cell_vec_formula_valid_count": 26580,
        "cell_vec_examples": [
          {
            "time": 60,
            "slot": 0,
            "x": 81.71924,
            "y": 151.4685,
            "cellX": 81,
            "vecX": 92.0627,
            "cellY": 151,
            "vecY": 59.968,
            "reconstructed_x": 81.71924,
            "reconstructed_y": 151.4685
          },
          {
            "time": 60,
            "slot": 1,
            "x": 84.37915,
            "y": 160.6626,
            "cellX": 84,
            "vecX": 48.5312,
            "cellY": 160,
            "vecY": 84.8128,
            "reconstructed_x": 84.37915,
            "reconstructed_y": 160.6626
          },
          {
            "time": 60,
            "slot": 2,
            "x": 120.255615,
            "y": 123.20703,
            "cellX": 120,
            "vecX": 32.7187,
            "cellY": 123,
            "vecY": 26.4998,
            "reconstructed_x": 120.255615,
            "reconstructed_y": 123.20703
          }
        ]
      },
      "crosscheck_deaths_pos": {
        "od_teamfights_count": 11,
        "od_total_deaths_pos_entries": 42,
        "matched_via_combatlog_death": 42,
        "exact_java_round_matches": 41,
        "exact_od_two_step_round_matches": 42,
        "within_1_cell": 42,
        "within_2_cells": 42,
        "raw_euclid_min": 0.2023,
        "raw_euclid_mean": 0.4082,
        "raw_euclid_max": 0.5858,
        "round_max_dx": 1,
        "round_max_dy": 0,
        "matched_via_lifestate": 42,
        "lifestate_euclid_mean": 1.1633,
        "lifestate_euclid_max": 10.6049,
        "samples": [
          {
            "tf_idx": 0,
            "slot": 4,
            "parser_xy": [
              144.792,
              81.948
            ],
            "parser_round_xy": [
              145,
              82
            ],
            "od_deaths_pos_xy": [
              145,
              82
            ],
            "euclid_err_raw": 0.215,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 5,
            "parser_xy": [
              154.73,
              86.538
            ],
            "parser_round_xy": [
              155,
              87
            ],
            "od_deaths_pos_xy": [
              155,
              87
            ],
            "euclid_err_raw": 0.535,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 6,
            "parser_xy": [
              96.335,
              174.353
            ],
            "parser_round_xy": [
              96,
              174
            ],
            "od_deaths_pos_xy": [
              96,
              174
            ],
            "euclid_err_raw": 0.487,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 1,
            "slot": 0,
            "parser_xy": [
              83.145,
              175.162
            ],
            "parser_round_xy": [
              83,
              175
            ],
            "od_deaths_pos_xy": [
              83,
              175
            ],
            "euclid_err_raw": 0.217,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 1,
            "slot": 1,
            "parser_xy": [
              82.78,
              168.25
            ],
            "parser_round_xy": [
              83,
              168
            ],
            "od_deaths_pos_xy": [
              83,
              168
            ],
            "euclid_err_raw": 0.333,
            "round_dx_dy": [
              0,
              0
            ]
          }
        ]
      },
      "crosscheck_obs_log": {
        "od_obs_log_count": 37,
        "parser_obs_count": 37,
        "matched_count": 37,
        "exact_01_round_matches": 37,
        "dx_max": 0.0467,
        "dy_max": 0.0472,
        "euclid_mean": 0.0379,
        "euclid_max": 0.0587,
        "samples": [
          {
            "time": 333,
            "slot": 1,
            "parser_xy": [
              96.258,
              154.497
            ],
            "od_obs_log_xy": [
              96.3,
              154.5
            ],
            "euclid_err": 0.042
          },
          {
            "time": 477,
            "slot": 1,
            "parser_xy": [
              132.493,
              114.633
            ],
            "od_obs_log_xy": [
              132.5,
              114.6
            ],
            "euclid_err": 0.0335
          },
          {
            "time": 1173,
            "slot": 1,
            "parser_xy": [
              116.779,
              127.158
            ],
            "od_obs_log_xy": [
              116.8,
              127.2
            ],
            "euclid_err": 0.0468
          },
          {
            "time": 1414,
            "slot": 1,
            "parser_xy": [
              156.417,
              95.085
            ],
            "od_obs_log_xy": [
              156.4,
              95.1
            ],
            "euclid_err": 0.0222
          },
          {
            "time": 1724,
            "slot": 1,
            "parser_xy": [
              135.796,
              155.877
            ],
            "od_obs_log_xy": [
              135.8,
              155.9
            ],
            "euclid_err": 0.0233
          }
        ]
      }
    },
    {
      "match_id": 9083213997,
      "patch": 60,
      "duration_sec": 2481,
      "start_time_utc": "2026-11-09T15:12:11+00:00",
      "replay_url_redacted": "http://replay153.valve.net/570/9083213997_<SALT_REDACTED>.dem.bz2",
      "download_sec": 0.638,
      "detected_payload_compression": "zstd",
      "decompress_tool": "zstd -d -f",
      "file_dem_bz2": "/tmp/m0_replay_work/replays/9083213997.dem.bz2: Zstandard compressed data (v0.8+), Dictionary ID: None",
      "file_dem": "/tmp/m0_replay_work/replays/9083213997.dem: data",
      "dem_magic_hex": "504244454d533200",
      "decompress_sec": 0.11,
      "parse_wall_sec": 2.847,
      "parse_time_l": {
        "raw_lines": [
          "SLF4J(W): No SLF4J providers were found.",
          "SLF4J(W): Defaulting to no-operation (NOP) logger implementation",
          "SLF4J(W): See https://www.slf4j.org/codes.html#noProviders for further details.",
          "        2.83 real         4.41 user         0.36 sys",
          "           571179008  maximum resident set size",
          "                   0  average shared memory size",
          "                   0  average unshared data size",
          "                   0  average unshared stack size",
          "               45804  page reclaims",
          "                   8  page faults",
          "                   0  swaps",
          "                   0  block input operations",
          "                   0  block output operations",
          "                   0  messages sent",
          "                   0  messages received",
          "                7981  signals received",
          "                 184  voluntary context switches",
          "               25962  involuntary context switches",
          "         59355443550  instructions retired",
          "         19995900189  cycles elapsed",
          "           560825616  peak memory footprint"
        ],
        "real_sec": 2.83,
        "user_sec": 4.41,
        "sys_sec": 0.36,
        "max_rss_bytes": 571179008,
        "max_rss_mib": 544.72,
        "peak_footprint_bytes": 560825616,
        "peak_footprint_mib": 534.84
      },
      "gzip_jsonl_sec": 0.374,
      "compact_01_gzip_sec": 0.051,
      "sizes_bytes": {
        "dem_bz2": 54316047,
        "dem": 96843120,
        "jsonl": 48143894,
        "jsonl_gz": 1943499,
        "compact_01_json_raw": 489973,
        "compact_01_json_gz": 132751,
        "compact_int_json_raw": 390919,
        "compact_int_json_gz": 97092
      },
      "jsonl_total_lines": 222945,
      "event_type_counts": {
        "actions": 114911,
        "DOTA_COMBATLOG_DAMAGE": 37415,
        "interval": 27140,
        "DOTA_COMBATLOG_MODIFIER_ADD": 10453,
        "DOTA_COMBATLOG_MODIFIER_REMOVE": 10397,
        "DOTA_COMBATLOG_HEAL": 6130,
        "DOTA_COMBATLOG_XP": 3973,
        "DOTA_COMBATLOG_DEATH": 3381,
        "DOTA_COMBATLOG_GOLD": 2604,
        "DOTA_COMBATLOG_ABILITY": 2129,
        "DOTA_COMBATLOG_ITEM": 1483,
        "DOTA_COMBATLOG_PURCHASE": 558,
        "DOTA_ABILITY_LEVEL": 458,
        "DOTA_COMBATLOG_PLAYERSTATS": 457,
        "assist_tick": 223,
        "DOTA_COMBATLOG_ABILITY_TRIGGER": 183,
        "pings": 115,
        "CHAT_MESSAGE_HERO_KILL": 96,
        "death_tick": 96,
        "sen": 66,
        "neutral_item_history": 65,
        "sen_left": 61,
        "STARTING_ITEM": 58,
        "CHAT_MESSAGE_ITEM_PURCHASE": 53,
        "CHAT_MESSAGE_RUNE_PICKUP": 49,
        "chatwheel": 45,
        "CHAT_MESSAGE_STREAK_KILL": 41,
        "obs": 36,
        "obs_left": 36,
        "CHAT_MESSAGE_SENTRY_WARD_KILLED": 32,
        "DOTA_COMBATLOG_TEAM_BUILDING_KILL": 28,
        "DOTA_COMBATLOG_KILLSTREAK": 26,
        "CHAT_MESSAGE_HERO_BANNED": 16,
        "DOTA_COMBATLOG_MULTIKILL": 14,
        "CHAT_MESSAGE_TOWER_KILL": 13,
        "CHAT_MESSAGE_OBSERVER_WARD_KILLED": 12,
        "DOTA_COMBATLOG_GAME_STATE": 10,
        "player_slot": 10,
        "CHAT_MESSAGE_DISCONNECT": 10,
        "CHAT_MESSAGE_RUNE_BOTTLE": 7,
        "CHAT_MESSAGE_GLYPH_USED": 7,
        "CHAT_MESSAGE_SMOKE_ACTIVATED": 7,
        "CHAT_MESSAGE_BUYBACK": 7,
        "DOTA_COMBATLOG_BUYBACK": 7,
        "CHAT_MESSAGE_SCAN_USED": 6,
        "CHAT_MESSAGE_BARRACKS_KILL": 6,
        "CHAT_MESSAGE_INTHEBAG": 5,
        "draft_start": 1,
        "CHAT_MESSAGE_FIRSTBLOOD": 1,
        "DOTA_COMBATLOG_FIRST_BLOOD": 1,
        "CHAT_MESSAGE_REPORT_REMINDER": 1,
        "CHAT_MESSAGE_INFORMATIONAL": 1,
        "CHAT_MESSAGE_TOWER_DENY": 1,
        "CHAT_MESSAGE_SUPER_CREEPS": 1,
        "cosmetics": 1,
        "dotaplus": 1,
        "epilogue": 1
      },
      "interval_analysis": {
        "all_keys_sorted": [
          "assists",
          "camps_stacked",
          "creeps_stacked",
          "deaths",
          "denies",
          "facet_hero_id",
          "firstblood_claimed",
          "gold",
          "hero_damage",
          "hero_id",
          "kills",
          "level",
          "lh",
          "life_state",
          "networth",
          "obs_placed",
          "observers_placed",
          "pred_vict",
          "randomed",
          "roshans_killed",
          "rune_pickups",
          "sen_placed",
          "slot",
          "stage",
          "stuns",
          "teamfight_participation",
          "time",
          "tower_damage",
          "towers_killed",
          "type",
          "unit",
          "variant",
          "x",
          "xp",
          "y"
        ],
        "sample_interval_entry": {
          "time": 0,
          "type": "interval",
          "unit": "CDOTA_Unit_Hero_Nyx_Assassin",
          "slot": 0,
          "gold": 0,
          "tower_damage": 0,
          "lh": 0,
          "xp": 0,
          "x": 115.765625,
          "y": 107.70996,
          "stuns": 2.2,
          "hero_id": 88,
          "variant": 0,
          "facet_hero_id": 88,
          "life_state": 0,
          "level": 1,
          "kills": 0,
          "deaths": 0,
          "assists": 0,
          "denies": 0,
          "obs_placed": 0,
          "sen_placed": 0,
          "creeps_stacked": 0,
          "camps_stacked": 0,
          "rune_pickups": 0,
          "randomed": false,
          "pred_vict": true,
          "firstblood_claimed": 0,
          "teamfight_participation": 0.0,
          "towers_killed": 0,
          "roshans_killed": 0,
          "observers_placed": 0,
          "networth": 600,
          "hero_damage": 146,
          "stage": 4
        },
        "dt_histogram_all": {
          "1": 27130
        },
        "dt_histogram_t_ge_0": {
          "1": 24820
        },
        "slots_summary": {
          "0": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "1": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "2": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "3": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "4": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "5": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "6": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "7": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "8": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          },
          "9": {
            "count_all": 2714,
            "count_t_ge_0": 2483,
            "min_t": -231,
            "max_t": 2482
          }
        },
        "coord_count": 25718,
        "min_x": 62.6267,
        "max_x": 192.9375,
        "min_y": 62.0681,
        "max_y": 191.3237,
        "in_64_192_count": 25606,
        "cell_vec_formula_valid_count": 25718,
        "cell_vec_examples": [
          {
            "time": 60,
            "slot": 0,
            "x": 85.188965,
            "y": 157.61719,
            "cellX": 85,
            "vecX": 24.1875,
            "cellY": 157,
            "vecY": 79.0003,
            "reconstructed_x": 85.188965,
            "reconstructed_y": 157.61719
          },
          {
            "time": 60,
            "slot": 1,
            "x": 176.48438,
            "y": 89.514404,
            "cellX": 176,
            "vecX": 62.0006,
            "cellY": 89,
            "vecY": 65.8437,
            "reconstructed_x": 176.48438,
            "reconstructed_y": 89.514404
          },
          {
            "time": 60,
            "slot": 2,
            "x": 121.77002,
            "y": 118.94922,
            "cellX": 121,
            "vecX": 98.5626,
            "cellY": 118,
            "vecY": 121.5002,
            "reconstructed_x": 121.77002,
            "reconstructed_y": 118.94922
          }
        ]
      },
      "crosscheck_deaths_pos": {
        "od_teamfights_count": 11,
        "od_total_deaths_pos_entries": 52,
        "matched_via_combatlog_death": 52,
        "exact_java_round_matches": 49,
        "exact_od_two_step_round_matches": 52,
        "within_1_cell": 52,
        "within_2_cells": 52,
        "raw_euclid_min": 0.1704,
        "raw_euclid_mean": 0.3745,
        "raw_euclid_max": 0.6087,
        "round_max_dx": 0,
        "round_max_dy": 1,
        "matched_via_lifestate": 52,
        "lifestate_euclid_mean": 0.8004,
        "lifestate_euclid_max": 4.402,
        "samples": [
          {
            "tf_idx": 0,
            "slot": 1,
            "parser_xy": [
              164.794,
              75.177
            ],
            "parser_round_xy": [
              165,
              75
            ],
            "od_deaths_pos_xy": [
              165,
              75
            ],
            "euclid_err_raw": 0.272,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 2,
            "parser_xy": [
              181.305,
              98.789
            ],
            "parser_round_xy": [
              181,
              99
            ],
            "od_deaths_pos_xy": [
              181,
              99
            ],
            "euclid_err_raw": 0.371,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 4,
            "parser_xy": [
              177.095,
              102.26
            ],
            "parser_round_xy": [
              177,
              102
            ],
            "od_deaths_pos_xy": [
              177,
              102
            ],
            "euclid_err_raw": 0.277,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 0,
            "slot": 6,
            "parser_xy": [
              176.821,
              105.337
            ],
            "parser_round_xy": [
              177,
              105
            ],
            "od_deaths_pos_xy": [
              177,
              105
            ],
            "euclid_err_raw": 0.382,
            "round_dx_dy": [
              0,
              0
            ]
          },
          {
            "tf_idx": 1,
            "slot": 0,
            "parser_xy": [
              97.637,
              161.393
            ],
            "parser_round_xy": [
              98,
              161
            ],
            "od_deaths_pos_xy": [
              98,
              161
            ],
            "euclid_err_raw": 0.535,
            "round_dx_dy": [
              0,
              0
            ]
          }
        ]
      },
      "crosscheck_obs_log": {
        "od_obs_log_count": 36,
        "parser_obs_count": 36,
        "matched_count": 36,
        "exact_01_round_matches": 36,
        "dx_max": 0.0491,
        "dy_max": 0.0496,
        "euclid_mean": 0.0354,
        "euclid_max": 0.0643,
        "samples": [
          {
            "time": 25,
            "slot": 0,
            "parser_xy": [
              119.528,
              139.033
            ],
            "od_obs_log_xy": [
              119.5,
              139.0
            ],
            "euclid_err": 0.0434
          },
          {
            "time": 927,
            "slot": 0,
            "parser_xy": [
              94.089,
              120.214
            ],
            "od_obs_log_xy": [
              94.1,
              120.2
            ],
            "euclid_err": 0.0176
          },
          {
            "time": 948,
            "slot": 0,
            "parser_xy": [
              111.216,
              127.935
            ],
            "od_obs_log_xy": [
              111.2,
              127.9
            ],
            "euclid_err": 0.0382
          },
          {
            "time": 1343,
            "slot": 0,
            "parser_xy": [
              78.469,
              183.194
            ],
            "od_obs_log_xy": [
              78.5,
              183.2
            ],
            "euclid_err": 0.0316
          },
          {
            "time": 1440,
            "slot": 0,
            "parser_xy": [
              168.807,
              102.53
            ],
            "od_obs_log_xy": [
              168.8,
              102.5
            ],
            "euclid_err": 0.031
          }
        ]
      }
    }
  ],
  "excerpt_9083213997": {
    "excerpt_path": "/private/tmp/wt_m0_replay/tools/replay_lab/sample_9083213997_excerpt.jsonl",
    "line_count": 181,
    "bytes": 68246,
    "type_counts": {
      "interval": 80,
      "pings": 15,
      "obs": 15,
      "DOTA_COMBATLOG_DEATH": 15,
      "obs_left": 15,
      "DOTA_COMBATLOG_ITEM": 10,
      "DOTA_COMBATLOG_DAMAGE": 10,
      "DOTA_COMBATLOG_MODIFIER_ADD": 8,
      "DOTA_COMBATLOG_MODIFIER_REMOVE": 7,
      "DOTA_COMBATLOG_ABILITY": 6
    },
    "pii_needles_checked": 33,
    "pii_hits": 0
  }
}
```

</details>

### 附录 3：Valve 录像保留期探针与 28 天场次统计完整输出（`python3 tools/replay_lab/check_retention_and_volume.py`）

```text
$ python3 tools/replay_lab/check_retention_and_volume.py
=== M0 RETENTION & STORAGE PROBE ===
Runtime UTC Timestamp : 2026-11-15T11:06:05.070216+00:00
Roster Source         : roster.json (11 account IDs -> 10 canonical members via account_aliases)
Sanitization          : Player nicknames, account IDs, and replay_url/salt tokens strictly omitted

--- PART A: MATCH VOLUME TALLY (DEFAULT /players/{aid}/matches?date=35) ---
Window             Total Unique  Roster >=2  Parsed >=2   5-Roster  party_size=5
--------------------------------------------------------------------------------
<= 3.00d                      1           1           1          0             0
Week -1 (0-7d]               15          13           6          3             4
Week -2 (7-14d]              57          27          13          7             8
Week -3 (14-21d]             46          21          14          4             4
Week -4 (21-28d]             67          16          10          2             2
Past 28d Total              185          77          43         16            18
Past 35d Total              230          99          57         23            26

--- PART B: ALL-MODES COMPARISON (significant=0, includes Turbo/AD) ---
Window             Total Unique  Roster >=2  Parsed >=2   5-Roster  party_size=5
--------------------------------------------------------------------------------
<= 3.00d                      2           1           1          0             0
Week -1 (0-7d]               18          15           6          3             4
Week -2 (7-14d]              62          30          13          8             8
Week -3 (14-21d]             49          22          15          4             4
Week -4 (21-28d]             68          17          10          2             2
Past 28d Total              197          84          44         17            18
Past 35d Total              248         106          58         24            26

--- PART A2: PAST 28D ROSTER STACK-SIZE DISTRIBUTION (ANONYMOUS) ---
Roster Stack (same team)     Default (?date=35)  All-Modes (sig=0)
--------------------------------------------------------------------
1-roster (solo/external)                    108                113
2-roster                                     29                 31
3-roster                                     22                 22
4-roster                                     10                 14
5-roster                                     16                 17

[NOTE] Target 1d: 0 roster matches found in [0.00d, 2.00d]; using closest available >=2 squad match (and newest sig=0 solo match if newer).
--- PART C: VALVE REPLAY RETENTION PROBE (HEAD ONLY, TARGETS 1/3/7/10/14/21d) ---
Bucket                          Match ID  Age(d) Stack OD Status  Patch Cluster   HTTP  Content-Length Replay URL
-----------------------------------------------------------------------------------------------------------------
1d (newest sig=0 solo)        9087860371    2.19     1  unparsed   7.41     151    N/A               - replay_url=None (unparsed on OpenDota)
1d (closest >=2)              9087090072    2.82     2       v22   7.41     154    200      54,071,426 present
3d (next >=2)                 9085834639    3.80     3       v22   7.41     152    200      52,132,535 present
7d (closest >=2, unparsed)    9081263873    7.12     2  unparsed   7.41     151    200      49,841,531 present
7d (parsed >=2)               9081933680    6.80     5       v22   7.41     154    200      43,728,225 present
10d (closest >=2)             9077212017    9.90     5       v22   7.41     153    200      39,386,272 present
14d (closest >=2, unparsed)   9071559155   13.94     2  unparsed   7.41     153    200      59,321,415 present
14d (parsed >=2)              9071281304   14.08     3       v22   7.41     153    200      48,418,271 present
21d (closest >=2)             9061341080   20.91     3       v22   7.41     151    200      39,128,379 present

--- PART D: EXTENDED RETENTION BOUNDARY CHECK (28d-180d, HEAD ONLY) ---
Bucket                          Match ID  Age(d) Stack OD Status  Patch Cluster   HTTP  Content-Length Replay URL
-----------------------------------------------------------------------------------------------------------------
Ext 28d (parsed >=2)          9051134110   27.84     2       v22   7.41     152    200      37,378,742 present
Ext 35d (parsed >=2)          9040451712   34.76     2       v22   7.41     151    200      70,917,422 present
Ext ~60d (boundary)           9001731016   59.86   n/a       v22   7.41     154    200      33,313,623 present
Ext ~91.5d (boundary)         8947636518   91.63   n/a       v22   7.41     153    200      56,821,303 present
Ext ~100.5d (boundary)        8932348500  100.82   n/a  unparsed   7.41     151    200      38,346,024 present
Ext ~103.5d (boundary)        8927541236  103.89   n/a  unparsed   7.41     151    404               - present
Ext ~180d (boundary)          8817458915  179.80   n/a  unparsed   7.41     152    404               - present

--- PART E: MEASURED .dem.bz2 PAYLOAD SIZE & EMPIRICAL RETENTION SUMMARY ---
HTTP 200 samples          : 13
Min / Median / Mean / Max : 31.77 MiB / 46.18 MiB / 45.69 MiB / 67.63 MiB
Observed Valve CDN window : HTTP 200 up to 100.82d; HTTP 404/410 from 103.89d onward
```

### 附录 4：GitHub Actions `ubuntu-latest` Run `43707314979` 匿名日志输出（`gh run view 43707314979 --log`）

<details>
<summary>点击展开 Run 43707314979 完整工具校验、构建 SHA、匿名基准 JSON 及清理步骤原文（已过滤 Maven central 下载进度行）</summary>

```text
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5358228Z if ! command -v /usr/bin/time >/dev/null 2>&1 || ! command -v bzip2 >/dev/null 2>&1 || ! command -v zstd >/dev/null 2>&1; then
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5359176Z   sudo apt-get update
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5359657Z   sudo apt-get install -y time bzip2 zstd
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5360143Z fi
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5360509Z /usr/bin/time --version | head -n 1
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5361053Z bzip2 --version </dev/null 2>&1 | head -n 1
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5361815Z zstd --version
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5362193Z mvn -version
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5489993Z shell: /usr/bin/bash -e {0}
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5490583Z env:
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5760663Z time (GNU Time) UNKNOWN
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5861260Z bzip2, a block-sorting file compressor.  Version 1.0.8, 13-Jul-2019.
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:56.5875971Z *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:58.6955366Z Apache Maven 3.9.15 (98b2cdbfdb5f1ac8781f537ea9acccaed7922349)
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:58.6956082Z Maven home: /usr/share/apache-maven-3.9.15
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:58.6956922Z Java version: 21.0.13, vendor: Eclipse Adoptium, runtime: /usr/lib/jvm/temurin-21-jdk-amd64
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:58.6960735Z Default locale: en, platform encoding: UTF-8
bench	Ensure GNU time, bzip2, and zstd are installed	2026-11-15T11:06:58.6961709Z OS name: "linux", version: "7.0.0-1019-azure", arch: "amd64", family: "unix"
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7245821Z rm -rf /tmp/m0_gha_parser
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7246254Z git clone --depth 1 https://github.com/odota/parser.git /tmp/m0_gha_parser
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7246710Z git -C /tmp/m0_gha_parser rev-parse HEAD
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7247112Z mvn -q -f /tmp/m0_gha_parser/pom.xml package -DskipTests
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7247493Z mkdir -p /tmp/m0_gha_parser/cli_classes
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7248094Z javac -proc:none -cp /tmp/m0_gha_parser/target/stats-0.1.0.jar -d /tmp/m0_gha_parser/cli_classes tools/replay_lab/ParseCli.java
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7303520Z shell: /usr/bin/bash -e {0}
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7303786Z env:
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:58.7411429Z Cloning into '/tmp/m0_gha_parser'...
bench	Clone and build odota/parser + ParseCli	2026-11-15T11:06:59.1638244Z 67945be040de92d0ba9cdedc77434886d4f736be
bench	Run anonymous replay benchmark	2026-11-15T11:07:20.6884122Z python3 tools/replay_lab/gha_m0_bench.py
bench	Run anonymous replay benchmark	2026-11-15T11:07:20.6939346Z shell: /usr/bin/bash -e {0}
bench	Run anonymous replay benchmark	2026-11-15T11:07:20.6939618Z env:
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0315916Z {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0316412Z   "utc_run_at": "2026-11-15T11:08:32.006026+00:00",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0316844Z   "host": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0317245Z     "platform": "Linux-7.0.0-1019-azure-x86_64-with-glibc2.43",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0317765Z     "machine": "x86_64",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0318111Z     "cpu_count": 4,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0318446Z     "MemTotal": "16366640 kB",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0318893Z     "MemAvailable": "15106332 kB",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0319355Z     "cpu_model": "AMD EPYC 9V74 80-Core Processor"
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0319808Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0320969Z   "java_version": "openjdk version \"21.0.13\" 2026-10-20 LTS | OpenJDK Runtime Environment Temurin-21.0.13+9 (build 21.0.13+9-LTS) | OpenJDK 64-Bit Server VM Temurin-21.0.13+9 (build 21.0.13+9-LTS, mixed mode, sharing)",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0322414Z   "odota_parser_commit": "67945be040de92d0ba9cdedc77434886d4f736be",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0322997Z   "selected_match_anonymous": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0323394Z     "patch": 60,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0323733Z     "duration_sec": 2616,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0324100Z     "squad_roster_count": 2,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0324463Z     "head_status": 200
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0325012Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0325351Z   "detected_payload_compression": "zstd",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0325818Z   "decompress_tool": "zstd -d -f",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0326231Z   "durations_sec": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0326557Z     "download_dem_bz2": 61.398,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0326941Z     "decompress": 0.133,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0335505Z     "parse_wall": 4.972,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0335949Z     "gzip9_jsonl": 0.866,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0336343Z     "compact_01_gzip9": 0.122
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0336724Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0337018Z   "sizes_bytes": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0337363Z     "dem_bz2": 54071426,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0337713Z     "dem": 91934749,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0338036Z     "jsonl": 52966593,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0338380Z     "jsonl_gz": 2156594,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0338730Z     "compact_01_json_raw": 526072,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0339112Z     "compact_01_json_gz": 145622,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0339473Z     "compact_int_json_raw": 421521,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0339846Z     "compact_int_json_gz": 106784
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0340185Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0340469Z   "jsonl_total_lines": 210452,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0340855Z   "event_type_counts": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0341244Z     "actions": 84966,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0341618Z     "DOTA_COMBATLOG_DAMAGE": 40288,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0341993Z     "interval": 28400,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0342340Z     "DOTA_COMBATLOG_MODIFIER_ADD": 16118,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0342830Z     "DOTA_COMBATLOG_MODIFIER_REMOVE": 16102,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0343314Z     "DOTA_COMBATLOG_ABILITY": 4449,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0372255Z     "DOTA_COMBATLOG_XP": 4371,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0372855Z     "DOTA_COMBATLOG_HEAL": 4367,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0373294Z     "DOTA_COMBATLOG_DEATH": 4259,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0373734Z     "DOTA_COMBATLOG_GOLD": 3262,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0374164Z     "DOTA_COMBATLOG_ITEM": 1375,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0375244Z     "DOTA_COMBATLOG_PURCHASE": 570,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0375664Z     "DOTA_ABILITY_LEVEL": 424,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0376060Z     "DOTA_COMBATLOG_PLAYERSTATS": 317,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0376478Z     "pings": 170,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0376799Z     "assist_tick": 134,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0377141Z     "sen": 72,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0377456Z     "neutral_item_history": 70,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0377842Z     "CHAT_MESSAGE_HERO_KILL": 69,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0378273Z     "death_tick": 69,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0378604Z     "sen_left": 66,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0378940Z     "CHAT_MESSAGE_ITEM_PURCHASE": 60,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0379593Z     "CHAT_MESSAGE_RUNE_PICKUP": 53,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0379998Z     "STARTING_ITEM": 53,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0380367Z     "chatwheel": 52,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0380681Z     "obs": 39,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0381062Z     "obs_left": 38,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0381406Z     "CHAT_MESSAGE_STREAK_KILL": 26,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0381825Z     "CHAT_MESSAGE_SENTRY_WARD_KILLED": 22,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0382291Z     "DOTA_COMBATLOG_TEAM_BUILDING_KILL": 19,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0382762Z     "DOTA_COMBATLOG_KILLSTREAK": 18,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0383203Z     "CHAT_MESSAGE_HERO_BANNED": 16,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0383658Z     "CHAT_MESSAGE_OBSERVER_WARD_KILLED": 13,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0384130Z     "CHAT_MESSAGE_TOWER_KILL": 12,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0385441Z     "DOTA_COMBATLOG_GAME_STATE": 10,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0385883Z     "player_slot": 10,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0386260Z     "CHAT_MESSAGE_SMOKE_ACTIVATED": 10,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0386707Z     "CHAT_MESSAGE_DISCONNECT": 10,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0387135Z     "CHAT_MESSAGE_RUNE_BOTTLE": 9,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0387545Z     "DOTA_COMBATLOG_MULTIKILL": 9,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0387943Z     "CHAT_MESSAGE_SCAN_USED": 7,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0388338Z     "chat": 5,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0388676Z     "CHAT_MESSAGE_PAUSE_COUNTDOWN": 4,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0389110Z     "CHAT_MESSAGE_GLYPH_USED": 4,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0389534Z     "DOTA_COMBATLOG_ABILITY_TRIGGER": 4,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0389990Z     "CHAT_MESSAGE_BARRACKS_KILL": 4,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0390428Z     "CHAT_MESSAGE_UNPAUSE_COUNTDOWN": 3,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0390855Z     "CHAT_MESSAGE_INTHEBAG": 2,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0391254Z     "CHAT_MESSAGE_BUYBACK": 2,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0391652Z     "DOTA_COMBATLOG_BUYBACK": 2,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0392039Z     "draft_start": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0392417Z     "CHAT_MESSAGE_REPORT_REMINDER": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0392856Z     "CHAT_MESSAGE_INFORMATIONAL": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0393290Z     "CHAT_MESSAGE_FIRSTBLOOD": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0393717Z     "DOTA_COMBATLOG_FIRST_BLOOD": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0394143Z     "CHAT_MESSAGE_RUNE_DENY": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0394727Z     "CHAT_MESSAGE_PAUSED": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0395131Z     "CHAT_MESSAGE_UNPAUSED": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0395518Z     "game_paused": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0395853Z     "CHAT_MESSAGE_TOWER_DENY": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0396274Z     "CHAT_MESSAGE_COURIER_LOST": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0396746Z     "CHAT_MESSAGE_COURIER_RESPAWNED": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0397211Z     "CHAT_MESSAGE_ROSHAN_KILL": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0397639Z     "CHAT_MESSAGE_AEGIS": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0398040Z     "CHAT_MESSAGE_MINIBOSS_KILL": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0398466Z     "cosmetics": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0398806Z     "dotaplus": 1,
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0399137Z     "epilogue": 1
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0399444Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0399727Z   "interval_dt_t_ge_0": {
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0400085Z     "1": 26170
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0400364Z   },
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0400671Z   "gnu_time_v_lines": [
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0401797Z     "\tCommand being timed: \"java -cp /tmp/m0_gha_parser/target/stats-0.1.0.jar:/tmp/m0_gha_parser/cli_classes ParseCli /tmp/m0_gha/replay.dem /tmp/m0_gha/parsed.jsonl\"",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0402927Z     "\tUser time (seconds): 10.56",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0403363Z     "\tSystem time (seconds): 0.58",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0403808Z     "\tPercent of CPU this job got: 224%",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0404740Z     "\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:04.97",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0405301Z     "\tAverage shared text size (kbytes): 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0405784Z     "\tAverage unshared data size (kbytes): 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0406284Z     "\tAverage stack size (kbytes): 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0406714Z     "\tAverage total size (kbytes): 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0407209Z     "\tMaximum resident set size (kbytes): 649912",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0407756Z     "\tAverage resident set size (kbytes): 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0408278Z     "\tMajor (requiring I/O) page faults: 2",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0408771Z     "\tMinor (reclaiming a frame) page faults: 163354",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0409523Z     "\tVoluntary context switches: 4103",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0409981Z     "\tInvoluntary context switches: 458",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0410411Z     "\tSwaps: 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0410753Z     "\tFile system inputs: 744",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0411164Z     "\tFile system outputs: 104072",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0411598Z     "\tSocket messages sent: 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0412013Z     "\tSocket messages received: 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0412448Z     "\tSignals delivered: 0",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0412841Z     "\tPage size (bytes): 4096",
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0413228Z     "\tExit status: 0"
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0413553Z   ]
bench	Run anonymous replay benchmark	2026-11-15T11:08:32.0413823Z }
bench	Clean up temporary files	2026-11-15T11:08:32.0485137Z rm -rf /tmp/m0_gha /tmp/m0_gha_parser
bench	Clean up temporary files	2026-11-15T11:08:32.0539146Z shell: /usr/bin/bash -e {0}
bench	Clean up temporary files	2026-11-15T11:08:32.0539407Z env:
```

</details>
