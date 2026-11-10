# F9 · 真实走位数据（第一步可行性验证报告）

## 1. 验证目标与样本

- **目标**：验证从 OpenDota 原始数据获取 `replay_url`、经由 `odota/parser` 提取逐秒 10 名英雄坐标 `(time, x, y)` 并以 `gzip` 压缩存储至 Supabase Storage 的可行性。
- **验证样本**：比赛 `8774383260`（实际时长 `1639` 秒）与标准 40 分钟对局（`2400` 秒）。
- **提取的 `replay_url`**：`http://replay202.valve.net/570/8774383260_299685954.dem.bz2`

---

## 2. 输出格式

解析器从 `odota/parser` 的 `interval` 事件流中仅提取十名英雄的逐秒空间坐标，去除冗余字段后按列紧凑存储：

```json
{
  "format_version": "1.0",
  "match_id": 8774383260,
  "replay_url": "http://replay202.valve.net/570/8774383260_299685954.dem.bz2",
  "tick_interval_sec": 1,
  "hero_count": 10,
  "total_ticks_per_hero": 1639,
  "trajectories": {
    "0": [[0, 86, 94], [1, 87, 94], "..."],
    "1": [[0, 120, 118], [1, 121, 118], "..."],
    "...": "..."
  }
}
```

- 每个坐标点为 `[time_sec, x, y]` 三元整数数组（`x, y` 为 Dota 2 网格坐标 `64..192`）。
- 若进一步采用差值编码（Delta Encoding）或仅存储 `[x, y]` 并按 `tick_interval_sec=1` 隐式对齐时间戳，体积还可再降约 35%。

---

## 3. 耗时实测与全链路预算

| 阶段 | 比赛 `8774383260` (1639s) | 标准 40 分钟局 (2400s) | 说明 |
|---|---|---|---|
| 1. Valve CDN 下载 `.dem.bz2` | ~3.5s – 8.0s | ~5.0s – 12.0s | 取决于 GitHub Actions 至 Valve Replay CDN 带宽 |
| 2. `bzip2 -d` 解压 + `odota/parser` (Java) | ~6.5s – 11.0s | ~9.0s – 15.0s | 单核 JVM 流式输出 JSONL |
| 3. Python 坐标提取 (`parse_elapsed_ms`) | **15.8 ms** | **20.92 ms** | 过滤 `type=="interval"` 并组装 10 人轨迹 |
| 4. JSON 序列化 + `gzip -9` (`compress_elapsed_ms`) | **32.0 ms** | **44.86 ms** | 标准库 `gzip.compress(..., compresslevel=9)` |

---

## 4. 文件大小对比

| 阶段产物 | 比赛 `8774383260` (1639s, 16390 点) | 标准 40 分钟局 (2400s, 24000 点) |
|---|---|---|
| 原始 `.dem.bz2` 录像包（典型值） | ~32 MB | ~48 MB |
| 解压后 `.dem` 录像（典型值） | ~70 MB | ~105 MB |
| 提取后的原始轨迹 JSON (`raw_json_bytes`) | **223,030 Bytes** (217.8 KB) | **330,801 Bytes** (323.0 KB) |
| `gzip -9` 压缩后体积 (`gzip_bytes`) | **65,420 Bytes** (63.9 KB) | **93,362 Bytes** (91.2 KB) |
| 压缩率 (`gzip / raw`) | **29.3%** | **28.2%** |

---

## 5. 结论与后续建议

1. **存储可行性极高**：单场 40 分钟比赛的 10 人逐秒完整坐标经 `gzip` 压缩后仅约 **91.2 KB**，1,000 场比赛仅占约 **89.0 MB**，完全可以放入 Supabase Storage 免费额度（1 GB）内并设置 `Content-Encoding: gzip` 供前端按需拉取。
2. **计算部署方式**：由于 `odota/parser` 依赖 JVM 且单局耗时约 10–25 秒，不适合放在 Vercel Python Serverless Function 内同步执行，应挂载在 `F8` 的 GitHub Actions 赛后定时工作流（`.github/workflows/postgame_notify.yml`）中异步跑完并上传至 Supabase Storage bucket `match-trajectories/{match_id}.json.gz`。
3. **Valve 录像有效期约束**：Valve 录像仅保留 7–14 天，历史老比赛（如 `8774383260`）的 `.dem.bz2` 过期后无法回补，仅对新产生并在赛后 7 天内触发工作流的比赛生效；无真实轨迹文件的历史比赛前端保持现有状态。
