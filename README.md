# 刀塔账房（Dota 5-stack Ledger）

五黑战后复盘与赛前作战室——面向固定五黑车队的 Dota 2 赛后复盘、跨局个人/团队趋势追踪与赛前阵容分析工具。

## 架构概览与模块状态

- **后端引擎（零第三方依赖 Python 标准库）**：
  - `server.py` / `api/index.py`：HTTP 服务入口与 Vercel Serverless 适配层（所有写入与付费计算接口均需 `X-Team-Token` 鉴权，只读 `GET` 接口无外部写入与扣费副作用）。
  - `dota_analyst.py`：单局分析主编排、证据分级（`measured` / `inferred` / `template`）与统一花名册解析（`iter_roster_accounts`）。
  - `tactical_microscope_engine.py` + `microscope_sections/`：十三维战术显微镜分节模块（已完成按分节独立模块拆分）。
  - `draft_and_phase_coach.py`：跨局总账、赛前 BP 评估与数据来源标注。
  - `squad_growth_metrics.py`：团队指标、个人随局趋势曲线与最近 7 局目标追踪。
  - `ai_coach_engine.py`：多模型 AI 赛后判词生成与事件时间线事实核查。
  - `cloud_store.py` + `supabase_schema.sql`：Supabase 持久化层（报告、任务状态、全量历史 `player_matches`、个人目标 `player_goals`）。
- **前端工程状态**：
  - **前端尚未拆分**：单页状态、接口请求、各标签页渲染及时间轴回放逻辑目前仍集中在 `static/app.js`（配合 `static/index.html` 与 `static/styles.css`），全屏报告与 PDF 导出已通过打印样式复用页面 DOM；先前未被引用的 `static/modules/` 占位文件已清理。
  - 静态资源带内容哈希（由 `tools/build_static_hashes.py` 自动计算并同步更新 `static/index.html` 与 `vercel.json`）。

## 常用命令

```bash
# 运行全部单元测试
python3 -m unittest discover -s tests -v

# 校验静态资源内容哈希与引擎版本号
python3 tools/build_static_hashes.py --check
python3 tools/check_engine_version.py

# 前端语法检查与全栈健康检查
node --check static/app.js
python3 healthcheck_audit.py

# 增量同步车队全量历史对局（需联网访问 OpenDota，可选 --push-supabase 入库）
python3 tools/sync_full_match_history.py --push-supabase
```

## 商标声明

Dota 2 是 Valve 公司的商标，本站为玩家自用工具，与 Valve 无关。
