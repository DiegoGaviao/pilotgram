CREATE TABLE IF NOT EXISTS public.pg_profile_brief (
    ig_user_id TEXT PRIMARY KEY,
    niche TEXT NOT NULL DEFAULT '',
    target_audience TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    offer_summary TEXT NOT NULL DEFAULT '',
    preferred_language TEXT NOT NULL DEFAULT '',
    tone_style TEXT NOT NULL DEFAULT '',
    do_not_use_terms TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.pg_profile_brief ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.pg_profile_brief IS 'PG — questionário estratégico por IG (persistente em produção)';
