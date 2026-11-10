-- ============================================================================
-- Dota 2 战后算账 & 赛前锦囊 - Supabase PostgreSQL 数据库建表脚本 (supabase_schema.sql)
-- 在 Supabase Dashboard -> SQL Editor 中粘贴运行即可创建云端复盘表
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.dota_match_reports (
    match_id BIGINT PRIMARY KEY,
    engine_version TEXT NOT NULL DEFAULT '',
    focus_side TEXT NOT NULL DEFAULT 'dire',
    won BOOLEAN NOT NULL DEFAULT false,
    score TEXT NOT NULL DEFAULT '0:0',
    duration_str TEXT NOT NULL DEFAULT '',
    start_time_str TEXT NOT NULL DEFAULT '',
    is_parsed BOOLEAN NOT NULL DEFAULT true,
    has_grok BOOLEAN NOT NULL DEFAULT false,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.dota_match_reports
    ADD COLUMN IF NOT EXISTS engine_version TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_dota_match_reports_updated_at
    ON public.dota_match_reports (updated_at DESC);

ALTER TABLE public.dota_match_reports ENABLE ROW LEVEL SECURITY;

-- 允许服务端 service_role 完整读写，允许匿名客户端只读查询已生成的复盘
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'dota_match_reports' AND policyname = 'Allow public read dota_match_reports'
    ) THEN
        CREATE POLICY "Allow public read dota_match_reports"
            ON public.dota_match_reports FOR SELECT
            USING (true);
    END IF;
END
$$;

-- P3: 单场玩家结构化明细表（方便用 SQL 做跨局英雄/位置/胜率统计）
CREATE TABLE IF NOT EXISTS public.match_players (
    match_id BIGINT NOT NULL,
    player_slot SMALLINT NOT NULL,
    account_id BIGINT,
    personaname TEXT NOT NULL DEFAULT '',
    side TEXT NOT NULL DEFAULT 'radiant',
    pos SMALLINT NOT NULL DEFAULT 0,
    hero_id INTEGER NOT NULL DEFAULT 0,
    hero_short_zh TEXT NOT NULL DEFAULT '',
    won BOOLEAN NOT NULL DEFAULT false,
    kills INTEGER NOT NULL DEFAULT 0,
    deaths INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    net_worth INTEGER NOT NULL DEFAULT 0,
    gpm INTEGER NOT NULL DEFAULT 0,
    xpm INTEGER NOT NULL DEFAULT 0,
    hero_damage INTEGER NOT NULL DEFAULT 0,
    tower_damage INTEGER NOT NULL DEFAULT 0,
    score_100 NUMERIC(5, 1),
    blame_share_pct NUMERIC(5, 1) NOT NULL DEFAULT 0,
    contrib_share_pct NUMERIC(5, 1) NOT NULL DEFAULT 0,
    start_time_str TEXT NOT NULL DEFAULT '',
    duration_min NUMERIC(6, 1) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, player_slot)
);

CREATE INDEX IF NOT EXISTS idx_match_players_account_id
    ON public.match_players (account_id, match_id DESC);

CREATE INDEX IF NOT EXISTS idx_match_players_hero_id
    ON public.match_players (hero_id, won);

ALTER TABLE public.match_players ENABLE ROW LEVEL SECURITY;

-- A6: 异步 LLM 判词任务状态表
CREATE TABLE IF NOT EXISTS public.dota_llm_tasks (
    task_id TEXT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    side TEXT NOT NULL DEFAULT 'dire',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    task_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dota_llm_tasks_match_id
    ON public.dota_llm_tasks (match_id, updated_at DESC);

ALTER TABLE public.dota_llm_tasks ENABLE ROW LEVEL SECURITY;
