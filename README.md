# Pilotgram

**Repositório GitHub:** **próprio**, separado do Leads AI — vê **`REPO_GITHUB.md`** (criar `github.com/.../pilotgram` e primeiro `push`).  
**Passo a passo deploy:** **`PASSO_A_PASSO.md`**.  
**Fixar ao lado no Cursor:** **`LEIA_PRIMEIRO.md`**.

SaaS Dhawk para **Instagram** (planejar, gerar com IA, aprovar, publicar): **FastAPI** + **React/Vite** + **Supabase**. URL pública: **`https://www.dhawk.com.br/projetos/Pilotgram/`**.

## Variáveis de ambiente

**Supabase e chaves partilhadas:** os **mesmos valores** do Leads AI (`SUPABASE_*` no backend, anon no front). Pilotgram só acrescenta nomes `PG_*` / `VITE_PG_*` onde o código exige; tabelas **`pg_*`** no mesmo projeto. Detalhe em **`COPY_PASTE_PG.md`** (secção “Mesmo `.env` que o Leads AI?”).

## Stack

| Camada | Tecnologia |
|--------|------------|
| Front | Vite, React, Tailwind, `base: /projetos/Pilotgram/` |
| API | FastAPI, Instagram Graph API |
| Dados | Supabase Postgres (token solo em `pilotgram_oauth_solo`) ou SQLite em dev |
| Hospedagem front | Hostinger — pasta `public_html/projetos/Pilotgram/` |
| API | VPS Hostinger, Render, etc. |

## Fluxo actual (só produção Dhawk)

- **Site:** `https://www.dhawk.com.br/projetos/Pilotgram/`
- **OAuth Meta:** redirect só `https://www.dhawk.com.br/projetos/Pilotgram/oauth/callback` (sem localhost).
- **Build do front:** na raiz `PILOTGRAM/`, com `web/.env` preenchido (`VITE_PG_API_URL` = URL HTTPS da API), `cd web && npm run build` → enviar `dist/` ao Hostinger.
- **`npm run dev`** ainda funciona no PC para editar UI; em dev o front usa API em `127.0.0.1:8765` automaticamente, mas **login Meta em produção** exige o site já no domínio.

## Produção

1. Ordem recomendada: **`PASSO_A_PASSO.md`**.  
2. Detalhes extra: **`DEPLOY_DHAWK.md`**.

## Documentação extra

- **`COPY_PASTE_PG.md`** — SQL + `.env` backend/front + Meta (tudo para copiar; convenção **PG_** / **LA_**).
- **`PREREQUISITES.md`** — Instagram Criador/Empresa, OAuth, API Meta.
- **`DATA_ALIGNMENT_LEADS_AI.md`** — formato de dados alinhado ao Leads AI.
- **`schema.sql`** — esboço futuro multi-user (prefixo `igca_*` legado; migrar para `pilotgram_*` quando unificar no Supabase).

## Rebranding

Este projeto evoluiu do protótipo “IG Content Autopilot”. Pasta no disco: **`06_PROJETOS_ATIVOS/PILOTGRAM/`**.
