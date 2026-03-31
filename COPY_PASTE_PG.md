# Pilotgram — guia de cópia (PG_*) — **só produção (dhawk)**

**Prefixos:** `LA_` = Leads AI · `PG_` = Pilotgram · `META_` = app Meta  
**Tabelas Supabase Pilotgram:** `pg_*`

Não usamos mais OAuth em `localhost`; redirect Meta = **`https://www.dhawk.com.br/projetos/pilotgram/oauth/callback`**.

## Mesmo `.env` que o Leads AI?

Sim, para **Supabase** e chaves já partilhadas (IA, Resend, etc.): usa o **mesmo projeto** e os **mesmos valores** que em `LEADS_AI 2/SAAS_PLATFORM/backend/.env` e no front do Leads.

| O quê | Pilotgram |
|--------|-----------|
| **Postgres / URL / keys** | Mesmo `SUPABASE_URL`, **service role** no backend e **anon** no front — ou os equivalentes `PG_SUPABASE_*` / `VITE_PG_SUPABASE_*` com **os mesmos valores**. |
| **Backend** | `backend/config.py` aceita **`PG_SUPABASE_*` ou `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`** (e o alias `SUPABASE_KEY` como no Render do Leads). |
| **Só Pilotgram** | `META_OAUTH_REDIRECT_URI` deste produto, `PG_CORS_ORIGINS`, e na Meta o redirect extra do Pilotgram. `META_APP_ID` / `META_APP_SECRET` podem ser os **mesmos** do Leads se for o mesmo app. |
| **Tabelas** | Leads usa `la_*` (etc.); Pilotgram usa **`pg_*`** — convivem no mesmo Supabase. |

---

# Bloco 1 — SQL no Supabase

**Onde:** Supabase → SQL Editor → New query.

```
────────── COPIAR ABAIXO ──────────
```

```sql
CREATE TABLE IF NOT EXISTS public.pg_oauth_solo (
    id TEXT PRIMARY KEY DEFAULT 'solo',
    access_token TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.pg_oauth_solo ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.pg_oauth_solo IS 'PG — token OAuth Meta (solo)';
```

```
────────── COPIAR ATÉ AQUI ──────────
```

Clica **Run**.

---

# Bloco 2 — ficheiro `backend/.env` (servidor da API)

```
────────── COPIAR ABAIXO ──────────
```

```env
# Meta: podes reutilizar META_APP_ID / META_APP_SECRET do Leads (mesmo app).
META_APP_ID=
META_APP_SECRET=
META_OAUTH_REDIRECT_URI=https://www.dhawk.com.br/projetos/pilotgram/oauth/callback
META_GRAPH_VERSION=v21.0

PG_API_HOST=0.0.0.0
PG_API_PORT=8765
PG_CORS_ORIGINS=https://www.dhawk.com.br,https://dhawk.com.br

# URL HTTPS pública desta API (para o <img src> do criativo). No Render, RENDER_EXTERNAL_URL costuma bastar.
# PG_PUBLIC_API_URL=https://pilotgram.onrender.com

# Opcional: gerar imagem real via OpenAI Images (DALL·E), como nos teus testes com a API.
# OPENAI_API_KEY=
# PG_OPENAI_IMAGE_MODEL=dall-e-3

# Supabase: mesmos valores do backend Leads (ou deixa PG_* vazio e usa SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).
PG_SUPABASE_URL=https://SEU_REF.supabase.co
PG_SUPABASE_SERVICE_ROLE_KEY=
```

```
────────── COPIAR ATÉ AQUI ──────────
```

---

# Bloco 3 — ficheiro `web/.env` (antes de `npm run build`)

**Obrigatório:** `VITE_PG_API_URL` = URL **HTTPS** pública da FastAPI (sem `/` no fim).

```
────────── COPIAR ABAIXO ──────────
```

```env
VITE_PG_API_URL=https://URL-PUBLICA-DA-API-PILOTGRAM
# Mesma URL e chave anon / publishable que o front Leads (só o prefixo VITE_PG_* muda).
VITE_PG_SUPABASE_URL=https://SEU_REF.supabase.co
VITE_PG_SUPABASE_ANON_KEY=
```

```
────────── COPIAR ATÉ AQUI ──────────
```

---

# Bloco 4 — Meta (não é código)

**Onde:** developers.facebook.com → o teu app → Login Facebook → URIs válidos.

Adiciona **só** (sem apagar as do Leads AI):

`https://www.dhawk.com.br/projetos/pilotgram/oauth/callback`

---

# Bloco 5 — site no browser (utilizadores)

`https://www.dhawk.com.br/projetos/pilotgram/`

---

*SQL espelhado em:* `supabase/migrations/20260328120000_pilotgram_oauth_solo.sql`
