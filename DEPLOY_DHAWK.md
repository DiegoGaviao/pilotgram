# Pilotgram — deploy em dhawk.com.br

**Queres a ordem completa do início ao fim?** Abre primeiro **`PASSO_A_PASSO.md`**. Este ficheiro é o detalhe técnico por tema.

URL alvo: **`https://www.dhawk.com.br/projetos/pilotgram/`** (mesmo padrão do Leads AI).

## 1. Supabase

1. Usa o **mesmo projeto** que o Leads AI (URL + anon + service role) — só garante que correste a migração **`pg_oauth_solo`**. Cria projeto novo só se quiseres separar.
2. **SQL Editor** → cola e executa `supabase/migrations/20260328120000_pilotgram_oauth_solo.sql` (tabela **`pg_oauth_solo`**). Bloco único também em **`COPY_PASTE_PG.md`**.
3. Copia **Project URL**, **anon** (front) e **service_role** (só backend — nunca no front).

## 2. Build do front (dist)

Na raiz `PILOTGRAM/`:

```bash
cd web && npm install && npm run build
```

Saída: `web/dist/` — ficheiros estáticos com `base: /projetos/pilotgram/`.

## 3. Upload Hostinger (cPanel / File Manager)

1. No servidor, pasta pública (ex.: `public_html/projetos/`).
2. Cria diretório **`Pilotgram`** (respeita maiúsculas se o URL for assim).
3. Envia **todo o conteúdo** de `web/dist/` para `public_html/projetos/pilotgram/`.
4. Testa: `https://www.dhawk.com.br/projetos/pilotgram/` (deve carregar a SPA).

## 4. API FastAPI (Render ou VPS)

**Opção A — Render (rápido):** na raiz do projeto existe **`render.yaml`**. O código tem de estar num **repositório GitHub só do Pilotgram** — vê **`REPO_GITHUB.md`** (não uses o repo `leads-ai`). No [Render](https://render.com): New → Blueprint, escolhe **`DiegoGaviao/pilotgram`** (ou o nome que criaste), **Root Directory vazio**. Preenche as variáveis secretas (`META_APP_ID`, `META_APP_SECRET`, `PG_SUPABASE_*`). Copia a URL HTTPS do serviço (ex. `https://pilotgram-api.onrender.com`).

**Opção B — VPS Hostinger:** corre `uvicorn` atrás de **HTTPS** (Nginx + Let’s Encrypt ou painel). Mesmas variáveis que no `backend/.env.example` + segredos Meta/Supabase.

Em ambos os casos:

- `META_OAUTH_REDIRECT_URI=https://www.dhawk.com.br/projetos/pilotgram/oauth/callback`
- `PG_CORS_ORIGINS=https://www.dhawk.com.br,https://dhawk.com.br`

## 5. Front liga à API

No `web/.env` **antes** de `npm run build`:

```env
VITE_PG_API_URL=https://URL-HTTPS-DO-SERVIÇO-DA-API
VITE_PG_SUPABASE_URL=https://xxx.supabase.co
VITE_PG_SUPABASE_ANON_KEY=eyJ...
```

Volta a correr `npm run build` e faz upload do `dist`.

## 6. Meta for Developers

No app usado pelo Pilotgram, adiciona **Valid OAuth Redirect URI**:

`https://www.dhawk.com.br/projetos/pilotgram/oauth/callback`

(Pilotgram **não** usa redirect em `localhost`; só este URI na allowlist.)

## 7. React Router

O `vite.config` já usa `base: "/projetos/pilotgram/"` e o `BrowserRouter` usa `import.meta.env.BASE_URL` — não é preciso `homepage` extra.
