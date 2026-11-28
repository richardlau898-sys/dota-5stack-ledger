# 英雄攻略页

网址：`/heroes`，侧栏入口「英雄攻略 · 当前版本」。

点一个英雄，看当前版本高分段的：本版本官方改动、技能加点（每一次加点的选择比例、常见加点顺序、先主）、天赋（每一级两边的选择率和胜率）、中立物品（按等级）、附魔、终局出装和鞋子。可以分"全部 / 核心 / 辅助"看。

## 数据从哪来

| 内容 | 来源 |
|---|---|
| 比赛样本 | OpenDota 公开接口：`/publicMatches?min_rank=70` 取神话段以上的天梯全英雄选择比赛，`/matches/<id>` 取每场详情。未解析的比赛也带完整加点顺序（含天赋）、终局 6 格和背包、中立物品（`item_neutral`）、附魔（`item_neutral2`） |
| 当前版本 | OpenDota `/constants/patch`，取编号最大的版本；只统计这个版本的比赛 |
| 中文名、中立物品等级 | Valve 官方 `https://www.dota2.com/datafeed/`（`herolist`、`herodata`、`itemlist`，`language=schinese`）。天赋文字里的数值占位符用同一份数据里技能的 `special_values[].bonuses` 补全 |
| 本版本改动 | Valve 官方 `datafeed/patchnotes?version=<版本>&language=schinese`。只有更新日志的版本号和比赛的版本一致时才显示 |

不需要任何账号或密钥。

## 怎么更新

`.github/workflows/hero_builds.yml` 每 6 小时运行一次，合并到 main 时也会运行一次：

1. 从 Actions 缓存取回已抓过的比赛（只保留当前版本，最多 30,000 场，超出时删最早的）。
2. `tools/hero_builds/fetch_constants.py`：更新常量、官方中文数据和更新日志。
3. `tools/hero_builds/collect.py`：抓最多 450 场新比赛。按 OpenDota 返回头里的剩余额度限速（免费额度为每分钟 60 次、每天 3,000 次），每天至少留 300 次不用。最多抓 22 分钟：到时间、或剩余额度降到保留线时正常停下，已抓到的比赛照常进入汇总，不会让整次运行失败（整个任务的上限是 40 分钟；第一次运行抓 450 场用了 24 分钟）。
4. `tools/hero_builds/build.py`：汇总成一个 gzip JSON。
5. 上传到本仓库的 Release `hero-builds-data`（标为预发布，不会成为"最新版本"）。

网站（`hero_builds_store.py`）每 30 分钟最多从 Release 取一次。取不到时继续用上一次的数据，页面会提示"数据更新暂时失败"；一次都没取到过时，接口返回 503 和中文提示。

换版本后，第一次运行就会自动只统计新版本，开头几天样本会少，页面上会提示样本场数。

## 统计口径

- **样本：** 神话段及以上（`avg_rank_tier ≥ 70`）、天梯、全英雄选择、时长 15 分钟以上。
- **加点等级：** 不写死。每次从当期数据里算出"停在每一级的玩家通常加过几次点"（输出里的 `upgrades_at_level`），再由此给每一次加点标等级。7.42 和 7.41 就不一样：7.42 在 10 级会有两次加点，16、17、19、21–24、26 级不给点。
- **核心/辅助：** 推断的。按本队终局净值排名，前三为核心，后二为辅助。
- **中立物品和附魔：** 比赛结束时身上的那一件，不是整局的选择过程。
- **A 杖：** 按终局物品栏里有没有 A 杖统计。公开比赛数据里的 `aghanims_scepter` 标记几乎总是 0（2,700 名玩家里只有 2 个为真），不能用；吃掉的 A 杖看不到。魔晶用 `aghanims_shard` 标记，这个是正常的。
- **胜率：** 少于 20 场不显示。
- **出装：** 终局 6 格和背包里价格 1,200 及以上的装备，不含消耗品；鞋子单独统计。

## 已知局限

- 没有装备购买时间（公开比赛数据里没有），所以只有终局出装。
- 克制与搭配（英雄对英雄的胜率）暂时没做：样本分到一万多个英雄对上太稀，等每对能到 20 场以上再说。
- 公开仓库的定时工作流如果 60 天没有任何提交，GitHub 会自动停用；到时在 Actions 页面重新启用即可。

## 本地运行

```bash
python3 tools/hero_builds/fetch_constants.py --out .hero_const
python3 tools/hero_builds/collect.py --cache .hero_cache --max-matches 200
python3 tools/hero_builds/build.py --cache .hero_cache --const .hero_const --bundle .hero_out/hero_builds.json.gz
HERO_BUILDS_BUNDLE_URL=file://$PWD/.hero_out/hero_builds.json.gz python3 server.py
```

然后打开 `http://127.0.0.1:8788/heroes`。测试只用 `tests/fixtures/hero_builds/` 里的离线样本：`python3 -m unittest tests.test_hero_builds -v`。
