# Pilotgram — passo a passo

**URL do site:** `https://www.dhawk.com.br/projetos/Pilotgram/`  
**Redirect OAuth:** `https://www.dhawk.com.br/projetos/Pilotgram/oauth/callback`

**Supabase:** podes usar o **mesmo projeto** que o Leads AI; tabela **`pg_oauth_solo`**. Valores de URL/keys: iguais ao Leads — vê `COPY_PASTE_PG.md` (secção “Mesmo `.env`?”).

---

## Se já fizeste SQL + redirect na Meta

*(É o teu caso se já correste o script no Supabase e já adicionaste o URI válido no Facebook Login.)*

**Não repitas os passos de baixo “Supabase” e “Meta”.** Continua **daqui**:

| Ordem | O quê |
|------|--------|
| **1** | **API no ar** — cabeçalho *API no ar (Render ou VPS)* mais abaixo |
| **2** | **Front** — `web/.env` + `npm run build` — cabeçalho *Front: env e build* |
| **3** | **Hostinger** — cabeçalho *Upload no Hostinger* |
| **4** | **Teste OAuth** — cabeçalho *Teste OAuth* |

---

## Ainda não fizeste SQL nem redirect?

Só então segue **primeiro** estes dois blocos; depois volta ao quadro de cima.

### Supabase (uma vez)

1. [Supabase](https://supabase.com) → o teu projeto.
2. **SQL Editor** → cola o ficheiro **`supabase/migrations/20260328120000_pilotgram_oauth_solo.sql`** (ou **Bloco 1** de **`COPY_PASTE_PG.md`**) → **Run**.
3. Confirma que existe **`pg_oauth_solo`**.

### Meta (uma vez)

1. [developers.facebook.com](https://developers.facebook.com) → a tua app.
2. **Facebook Login** → **Valid OAuth Redirect URIs** → adiciona (sem apagar as do Leads):

   `https://www.dhawk.com.br/projetos/Pilotgram/oauth/callback`

---

## API no ar (Render ou VPS)

Precisas de uma URL **HTTPS** da FastAPI **antes** do build final do front.

### Opção A — Render

1. Tens de ter o código no GitHub num **repositório só do Pilotgram** (não o `leads-ai`). Passo a passo: **`REPO_GITHUB.md`**.
2. [render.com](https://render.com) → **New** → **Blueprint** (ou Web Service).
3. Escolhe o repo **`pilotgram`** (ou o nome que criaste). **Root Directory** = vazio (a raiz do repo já é o projeto).
3. Preenche segredos: `META_APP_ID`, `META_APP_SECRET`, `PG_SUPABASE_URL`, `PG_SUPABASE_SERVICE_ROLE_KEY` (mesmos do Leads / teu `.env`).
4. Confirma `META_OAUTH_REDIRECT_URI` e `PG_CORS_ORIGINS` alinhados ao `render.yaml` (Dhawk).
5. Copia a URL Live, ex. `https://pilotgram-api.onrender.com` — **sem `/` no fim**.

### Opção B — VPS

1. `pip install -r backend/requirements.txt`, **`backend/.env`** no servidor (Meta, Supabase, redirect Pilotgram, CORS).
2. `uvicorn` atrás de **HTTPS** (Nginx, etc.).
3. Anota o URL público **HTTPS**.

**Teste:** `https://SUA-API/health` → JSON com `status: ok` (ou equivalente).

---

## Front: env e build

1. **`PILOTGRAM/web/.env`**: `VITE_PG_API_URL` = URL do passo API; `VITE_PG_SUPABASE_*` = iguais ao front Leads.
2. Terminal:

```bash
cd PILOTGRAM/web
npm install
npm run build
```

3. Saída: **`web/dist/`**.

---

## Upload no Hostinger

1. `public_html/projetos/` → pasta **`Pilotgram`**.
2. Envia **todo** o conteúdo de **`web/dist/`** para lá.
3. Abre `https://www.dhawk.com.br/projetos/Pilotgram/`.

---

## Teste OAuth

1. No site, **Conectar Meta**.
2. Deves voltar a **`/projetos/Pilotgram/oauth/callback`** sem erro.
3. Se falhar redirect/URL bloqueada: confere Meta + `META_OAUTH_REDIRECT_URI` no backend (têm de coincidir).

---

## Onde está cada coisa

| Ficheiro | Conteúdo |
|----------|-----------|
| **`PASSO_A_PASSO.md`** | Este guia (com “já fiz SQL + redirect” em cima). |
| **`COPY_PASTE_PG.md`** | SQL e exemplos de `.env`. |
| **`DEPLOY_DHAWK.md`** | Detalhe técnico Hostinger / API. |
| **`render.yaml`** | Blueprint Render (`backend/`). |

---

## Se algo falhar

- **API / front:** `VITE_PG_API_URL` errado ou build **antes** de preencher → corrige `.env`, `npm run build`, volta a enviar `dist/`.
- **CORS:** `PG_CORS_ORIGINS` com `https://www.dhawk.com.br` (e `https://dhawk.com.br` se aplicável).
- **Meta:** redirect na app = `META_OAUTH_REDIRECT_URI` no servidor.
