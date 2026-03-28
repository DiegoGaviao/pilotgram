-- IG Content Autopilot — schema sugerido (Postgres / Supabase).
-- Prefixo igca_ para não colidir com outros SaaS no mesmo projeto.

CREATE TABLE IF NOT EXISTS igca_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS igca_meta_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES igca_users(id) ON DELETE CASCADE,
    fb_user_id TEXT NOT NULL,
    access_token_enc TEXT NOT NULL, -- criptografar em aplicação (não plain em prod)
    token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, fb_user_id)
);

CREATE TABLE IF NOT EXISTS igca_ig_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meta_account_id UUID NOT NULL REFERENCES igca_meta_accounts(id) ON DELETE CASCADE,
    ig_user_id TEXT NOT NULL,
    username TEXT,
    page_id TEXT NOT NULL,
    page_name TEXT,
    selected BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (meta_account_id, ig_user_id)
);

CREATE TABLE IF NOT EXISTS igca_media_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ig_profile_id UUID NOT NULL REFERENCES igca_ig_profiles(id) ON DELETE CASCADE,
    ig_media_id TEXT NOT NULL,
    caption TEXT,
    media_type TEXT,
    permalink TEXT,
    timestamp_utc TIMESTAMPTZ,
    like_count INT,
    comments_count INT,
    insights_json JSONB, -- reach, impressions, engagement quando disponível
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ig_profile_id, ig_media_id)
);

CREATE TABLE IF NOT EXISTS igca_briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ig_profile_id UUID NOT NULL REFERENCES igca_ig_profiles(id) ON DELETE CASCADE,
    payload_json JSONB NOT NULL, -- mesmo “shape” conceitual do onboarding Leads AI
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS igca_generated_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    briefing_id UUID REFERENCES igca_briefings(id) ON DELETE SET NULL,
    ig_profile_id UUID NOT NULL REFERENCES igca_ig_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft', -- draft | approved | scheduled | published | failed
    payload_json JSONB NOT NULL, -- legenda, tipo, image_url, etc.
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    meta_creation_id TEXT, -- id retornado pela API após publicar
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_igca_media_profile ON igca_media_snapshots(ig_profile_id);
CREATE INDEX IF NOT EXISTS idx_igca_posts_status ON igca_generated_posts(ig_profile_id, status);
