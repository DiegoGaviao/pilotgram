# Pilotgram — repositório **próprio** no GitHub (sem misturar com Leads AI)

O Pilotgram vive **só** nesta pasta. O repo **`leads-ai`** continua **só** para o Leads AI.

**Nota:** o assistente no Cursor **não** tem login na tua GitHub. Para “fazer por ti” no **teu** Mac, usa o script abaixo depois de `gh auth login`.

---

## 0. Automático (no teu terminal)

### Com GitHub CLI (`gh`)

1. Se aparecer *“Não encontrei o comando gh”*: `brew install gh` → `gh auth login`.
2. Na pasta do projeto:

```bash
cd "/Users/diegorufino/Desktop/DEV/2026/02 - Plano 2026/06_PROJETOS_ATIVOS/PILOTGRAM"
chmod +x scripts/push_github.sh
./scripts/push_github.sh
```

Isto cria **`pilotgram`** **privado** na conta com que fizeste login e faz o **primeiro push**. Outro nome: `GITHUB_REPO_NAME=meu-nome ./scripts/push_github.sh`

### Sem instalar `gh` (só `git`)

1. [github.com/new](https://github.com/new) → nome **`pilotgram`** → **sem** README → Create.
2. Na pasta do projeto:

```bash
cd "/Users/diegorufino/Desktop/DEV/2026/02 - Plano 2026/06_PROJETOS_ATIVOS/PILOTGRAM"
chmod +x scripts/push_sem_gh.sh
GIT_REMOTE=https://github.com/DiegoGaviao/pilotgram.git ./scripts/push_sem_gh.sh
```

(Ajusta `DiegoGaviao` se o teu utilizador for outro. O Git pode pedir login no browser ou token.)

---

## 1. Criar o repo vazio no GitHub (manual)

1. Entra em [github.com/new](https://github.com/new).
2. **Repository name:** por exemplo `pilotgram` (fica `github.com/DiegoGaviao/pilotgram`).
3. **Público** ou **Privado** — como preferires.
4. **Não** marques “Add a README” (evita conflito no primeiro push; já tens `README.md` aqui).
5. Cria o repositório.

---

## 2. Na tua máquina — Git só dentro de `PILOTGRAM/`

No terminal (ajusta o caminho se a tua pasta for outra):

```bash
cd "/Users/diegorufino/Desktop/DEV/2026/02 - Plano 2026/06_PROJETOS_ATIVOS/PILOTGRAM"

git init
git add .
git status   # confirma que NÃO aparecem .env, node_modules, dist, __pycache__
# Se correste `npm install` na raiz do PILOTGRAM, `node_modules/` na raiz tem de estar no .gitignore (já está).
git commit -m "chore: initial Pilotgram (FastAPI + Vite, repo próprio)"

git branch -M main
git remote add origin https://github.com/DiegoGaviao/pilotgram.git
git push -u origin main
```

Substitui **`DiegoGaviao/pilotgram`** pelo **utilizador/nome** que criaste no passo 1.

### Corrigir `origin` (GitHub avisou “repository moved”)

Se o `remote` tiver typo no user (`GaviaO` vs `Gaviao`):

```bash
git remote set-url origin https://github.com/DiegoGaviao/pilotgram.git
```

### Já fizeste push com `node_modules/` na raiz?

1. Garante que o `.gitignore` do projeto tem a linha **`node_modules/`** (já deve ter).
2. Na pasta PILOTGRAM:

```bash
git rm -r --cached node_modules
git add .gitignore
git commit -m "chore: deixar de versionar node_modules"
git push
```

Se o repo **só tem este commit** e queres apagar o histórico gordo de uma vez: em vez do commit acima, podes `git commit --amend` a juntar a remoção ao commit inicial e depois `git push --force` (só se tiveres a certeza que mais ninguém clonou).

---

## 3. Se o “Plano 2026” for outro Git na pasta pai

Tens um `.git` **dentro** de `PILOTGRAM/` e outro no repositório grande. Para o Git do **Plano** não tentar tratar o Pilotgram como pastas soltas:

- No `.gitignore` **na raiz do Plano 2026** (se existir), podes acrescentar uma linha:

```gitignore
06_PROJETOS_ATIVOS/PILOTGRAM/
```

Assim o histórico do Pilotgram fica **só** no GitHub `pilotgram`, sem duplicar no monorepo.

---

## 4. Render

- **New Web Service** (ou Blueprint) → escolhe **`DiegoGaviao/pilotgram`** (o repo **novo**).
- **Root Directory:** deixa **vazio** (a raiz do repo **é** já o projeto Pilotgram).
- O ficheiro **`render.yaml`** na raiz aponta `rootDir: backend` — mantém-se assim.

---

## 5. O que **nunca** commits

Já estão no `.gitignore` local:

- `backend/.env`, `web/.env`
- `web/node_modules/`, `web/dist/`
- `backend/data/`, venvs, `__pycache__`

Se algo sensível aparecer no `git status`, **não** faças `git add` disso.

---

Resumo: **repo GitHub novo só para Pilotgram** → `git init` **nesta pasta** → `push` → no Render liga **esse** repo, **não** o `leads-ai`.
