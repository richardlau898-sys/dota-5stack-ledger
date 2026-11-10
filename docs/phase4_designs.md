# 阶段 4（F1–F10）功能设计说明书

所有统计指标严格遵守 `T1-9` 最小样本量规则（样本局数 `< 10` 局时只显示原始局数与胜负场次，不下定性结论、不贴绝活/冥币标签）以及 `AGENTS.md` 数据诚实原则（无数据输出 `null`，界面显示“无数据”）。

---

## F1 · 导入全量历史

- **数据来源**：OpenDota `GET /api/players/{account_id}/matches`，无需解析 `.dem` 录像。查询参数：
  - `significant=0`（包含全部模式与匹配类型）
  - `included_account_id`（按队友账号筛选共同对局）
  - `project`：`["hero_id", "start_time", "duration", "player_slot", "radiant_win", "game_mode", "lobby_type", "kills", "deaths", "assists", "party_size", "lane_role", "is_roaming"]`
- **增量同步与限速**：
  - 免费额度限制：60 次/分钟、2,000 次/天（默认请求间隔 `>= 1.05s`，单日配额计数保存在 `.cache/opendota_sync_state.json`）。
  - 记录每个 `account_id` 已同步的最大 `match_id`，增量拉取时遇到 `<= max_synced_match_id` 即停止合并。
- **表结构 (`public.player_matches`)**：
  - 主键：`(account_id, match_id)`
  - 字段：`account_id BIGINT`, `match_id BIGINT`, `player_slot SMALLINT`, `radiant_win BOOLEAN`, `won BOOLEAN`, `hero_id INTEGER`, `hero_short_zh TEXT`, `pos SMALLINT`, `lane_role SMALLINT`, `kills INTEGER`, `deaths INTEGER`, `assists INTEGER`, `duration INTEGER`, `start_time BIGINT`, `game_mode SMALLINT`, `lobby_type SMALLINT`, `party_size SMALLINT`, `included_roster_ids JSONB`
- **统计指标定义**：
  - **每人英雄胜率**：按 `(account_id, hero_id)` 聚合 `games`, `wins`, `win_rate`（`<10` 局标记 `insufficient_sample: true`）。
  - **每人位置胜率**：按 `(account_id, pos)` 聚合 `games`, `wins`, `win_rate`。
  - **人数组合胜率**：按同局同阵营出现的花名册成员集合（2/3/4/5 人车队组合）聚合 `games`, `wins`, `win_rate`。

---

## F2 · 首屏“下一把要改的 3 件事”

- **数据来源**：单局报告中的实测数据（`measured` 证据等级结论，严禁混入 `inferred` 或 `template`）。
- **指标与排序定义**：
  - 候选池仅取本局 `evidence == "measured"` 的客观事实项（团战未按保命装 `unpressed_saves`、关键赢团后 90s 零建筑/肉山转化、买活后 60s 内再阵亡、视野断档期阵亡、10 分钟对线净值落后等）。
  - 排序权重：`team_scope_priority`（团队级 = 2，个人级 = 1）优先，同级按 `impact_score`（关联经济损失或阵亡数）降序取前 3 条。
  - 每条结构：`{"rank": 1..3, "scope": "team"|"player", "evidence": "measured", "timestamp_str": "MM:SS", "title": "...", "fact_detail": "...", "action_fix": "...", "impact_score": float}`。
- **界面草图**：在“内容核心总结 & 个人卷宗”首屏顶部（KPI 栏下方）展示 `next_game_top3_fixes` 三联卡片，每张卡片含 `[团队/个人]` 徽章、时间点芯片、实测证据与下一把可执行动作。

---

## F3 · 团队指标

- **数据来源**：OpenDota 单局 `teamfights`, `objectives`, `radiant_gold_adv`, `players[].buyback_log`, `players[].kills_log`, `players[].obs_log`, `players[].obs_left_log`, `players[].lh_t`, `players[].gold_t`。
- **7 项指标精确定义**：
  1. **赢团转化率 (`fight_conversion`)**：己方团战阵亡数比敌方少 `>= 2` 人的团战为“赢团”；检查团战 `end` 后 `[end, end + 90s]` 内 `objectives` 是否有己方建筑摧毁（`CHAT_MESSAGE_TOWER_KILL` / `CHAT_MESSAGE_BARRACKS_KILL`）或肉山击杀（`CHAT_MESSAGE_ROSHAN_KILL`）。
  2. **第一个肉山时间 (`first_roshan`)**：`objectives` 中首条 `CHAT_MESSAGE_ROSHAN_KILL` 的 `time`、`time_str` 与归属阵营（无肉山则为 `null`）。
  3. **翻盘局 (`throw_comeback_audit`)**：己方全场最大经济领先 `>= 10000` 金但最终落败的局（或落后 `>= 10000` 金翻盘获胜）；计算 `radiant_gold_adv` 任意 3 分钟滑动窗口 `[t, t+3]` 内己方经济跌幅最大的窗口及落在该窗口内的团战。
  4. **买活后再死 (`buyback_dieback`)**：同一玩家 `buyback_log` 时间 `t_bb` 到下一次阵亡时间 `t_death` 满足 `0 < t_death - t_bb <= 60` 秒。
  5. **开雾效果 (`smoke_effectiveness`)**：`purchase_log` / 物品使用中每次诡计之雾的时间窗口及结果统计。
  6. **高危眼位 (`high_risk_ward_spots`)**：跨局聚合 `obs_log` 与 `obs_left_log`（按网格坐标 `(x_bucket, y_bucket)` 归并），统计存活时间中位数 `< 120` 秒且样本数达标的固定高危眼位。
  7. **分路组合 (`lane_duo_networth_diff`)**：按真实同路队友组合与真实对位，统计 10 分钟净值差均值与局数。

---

## F4 · 个人趋势和每周目标

- **数据来源**：跨局历史复盘报告序列（按 `start_time` 升序排列）。
- **4 条个人随比赛变化曲线**：
  1. `non_teamfight_deaths_after_10m`：10 分钟后团战外阵亡次数。
  2. `lane_nw_diff_at_10m`：对真实对位的 10 分钟净值差。
  3. `support_wards_per_min`：辅助位（4/5 号位）每分钟插眼数（假眼+真眼/分钟，非辅助位为 `null`）。
  4. `key_item_timing_delta_sec`：关键装备（如 BKB/跳刀）完成时间相对本人历史中位数的偏差秒数。
- **每周目标 (`weekly_goals`)**：每人可设定 `metric_key` 与 `target_value`，对比近 7 天（或最近 N 局）均值计算达成率 `progress_pct` 与状态。

---

## F5 · BP 工具改用真实数据

- **数据来源**：
  1. 车队全量英雄池（来自 `F1` / 历史账本的真实英雄局数与胜率）。
  2. OpenDota `/players/{id}/heroes` 的 `against_games` 与 `against_win`（计算车队成员“最常输给谁”，遵守 `against_games >= 10` 最小样本量）。
  3. OpenDota `/heroStats`（保存在 `.cache/constants/hero_stats.json`）分段位真实选取数与胜率。
- **改动**：删除 `draft_and_phase_coach.py` 中 59 个手写英雄四维打分表与手写英雄 ID 克制表，全部改从真实历史胜率、`against_win` 与 `/heroStats` 派生。

---

## F6 · 时长画像和连打疲劳

- **数据来源**：`F1` 全量对局历史（`start_time`, `duration`, `won`）。
- **定义**：
  1. **比赛时长分桶 (`duration_buckets`)**：`<30m`、`30–40m`、`40–50m`、`>=50m` 四档的局数、胜场与胜率（遵守 `T1-9` 最小样本量 `<10` 局只展示局数不给结论）。
  2. **当晚第几局 (`session_game_buckets`)**：将对局按 `start_time` 升序排列，相邻两局开始时间间隔 `< 90` 分钟（`5400` 秒）归入同一晚 Session，统计第 1 局、第 2 局、第 3 局、第 4+ 局的局数与胜率。

---

## F7 · 每场 3 个复盘时刻

- **数据来源**：单局 `teamfights` 与 `radiant_gold_adv`。
- **定义**：按每波团战的绝对经济波动 `abs(gold_swing)` 降序选出前 3 波团战，输出 `top3_replay_moments`，每条包含 `rank`、`start_time_str`、`end_time_str`、`gold_swing`、`deaths_summary` 与一句完全中性的事实描述（供车队进 Dota 2 客户端跳时间轴看录像）。

---

## F8 · 赛后自动推送（D5）

- **流程**：`tools/postgame_webhook_notifier.py` + `.github/workflows/postgame_notify.yml` 定时检查 `roster.json` 成员最新比赛；发现新比赛时触发 OpenDota `/request/{match_id}` 解析，生成单局报告后向配置的 Webhook URL（Discord / 飞书 / 企业微信 / 通用 JSON Webhook）推送赛后摘要（比分、时长、前 3 个复盘时刻、`next_game_top3_fixes` 与报告链接）。

---

## F9 · 真实走位数据（可行性验证）

- **目标与做法**：编写 `tools/verify_replay_coordinates.py`，验证从比赛 `replay_url` 下载 `.dem.bz2`、通过 `odota/parser` 提取逐秒英雄坐标 `(time, slot, x, y)`、压缩为紧凑轨迹 JSON 的完整流水线，并输出实测/基准格式、耗时与体积报告。

---

## F10 · 账号合并和语气开关（D1）

- **账号合并**：`roster.json` 支持单个成员配置 `account_ids: [114933560, 86542163]`（或 `aliases`），跨局账本、单局认领与全量同步将同一成员名下的所有子账号合并统计（提供 `merge_accounts` 配置项）。
- **语气开关（按 D1）**：默认 `coach`（教练模式：只陈述客观事实与可执行建议，隐藏毒舌处刑海报入口）；用户可在视图栏手动开启 `roast`（毒舌模式：解锁处刑海报生成与犀利评语）。
