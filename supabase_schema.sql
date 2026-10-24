-- ============================================================================
-- Dota 2 战后算账 & 赛前锦囊 - Supabase PostgreSQL 数据库建表脚本 (supabase_schema.sql)
-- 在 Supabase Dashboard -> SQL Editor 中粘贴运行即可创建云端复盘表
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.dota_match_reports (
    match_id BIGINT PRIMARY KEY,
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
