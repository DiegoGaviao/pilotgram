-- Pilotgram — prefixo de tabelas: pg_ (LA_ = Leads AI no outro SaaS)
-- Colar no SQL Editor do Supabase e executar.

CREATE TABLE IF NOT EXISTS public.pg_oauth_solo (
    id TEXT PRIMARY KEY DEFAULT 'solo',
    access_token TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.pg_oauth_solo ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.pg_oauth_solo IS 'PG — token OAuth Meta (solo; multi-user depois com pg_* + auth)';

-- Se tinhas corrido a migração antiga (pilotgram_oauth_solo), podes remover manualmente:
-- DROP TABLE IF EXISTS public.pilotgram_oauth_solo;
