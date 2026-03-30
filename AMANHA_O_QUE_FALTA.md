# Pilotgram — quando abrires o projeto outra vez

Checklist para **funcionar de ponta a ponta** (site Dhawk + API Render + Meta).

## Atualização 2026-03-30 (correções críticas)

- Backend atualizado em `86123ea` (Render precisa deploy deste commit).
- Ajustes aplicados:
  - temas do DNA com filtro forte de stopwords (sem `your/this/about/...`);
  - detecção de idioma melhorada (evita mistura PT/EN);
  - legenda gerada com linguagem única por lote;
  - preview de criativo com fallback no frontend para não ficar em branco.
- ZIP frontend mais recente: `pilotgram_cpanel_20260330_1835.zip` em `../09_PILOTGRAM_DEPLOY/`.

## 1. Render (API)

- `META_APP_ID` e `META_APP_SECRET` preenchidos (app em developers.facebook.com).
- `META_OAUTH_REDIRECT_URI` = `https://www.dhawk.com.br/projetos/pilotgram/oauth/callback`
- `PG_CORS_ORIGINS` = `https://www.dhawk.com.br,https://dhawk.com.br`
- Depois de guardar: **deploy** do serviço.
- Testar: `https://pilotgram.onrender.com/health` → `"meta_app_configured": true`

## 2. Meta (Facebook Developers)

- Login do Facebook → **URIs de redirecionamento OAuth válidos** → incluir a mesma URL do redirect acima.

## 3. Mac — antes do ZIP (`web/.env`)

- `VITE_PG_API_URL=https://pilotgram.onrender.com` (sem barra no fim).
- Opcional: `VITE_PG_SUPABASE_*` se usares Supabase no front.

## 4. Gerar ZIP e Hostgator

```bash
cd "/Users/diegorufino/Desktop/DEV/2026/02 - Plano 2026/06_PROJETOS_ATIVOS/PILOTGRAM"
./scripts/package_hostgator.sh
```

- ZIP em `../09_PILOTGRAM_DEPLOY/`
- cPanel → `projetos/pilotgram/` → limpar → enviar ZIP → extrair na **raiz** de `pilotgram` (`index.html` + `.htaccess` + `assets/`).

## 5. Browser

- Preferir: `https://www.dhawk.com.br/projetos/pilotgram/`
- Se CSS/JS 404: cache limpo + ZIP da **mesma** build.

## Detalhe extra (docs longas)

- `COPY_PASTE_PG.md` — SQL Supabase, blocos `.env` backend/front.

---

*Quando perguntares ao assistente “o que falta para funcionar?”, podes dizer: lê `AMANHA_O_QUE_FALTA.md` nesta pasta.*
