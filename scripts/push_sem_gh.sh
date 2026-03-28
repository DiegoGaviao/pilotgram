#!/usr/bin/env bash
# Push só com git (sem GitHub CLI).
# 1) Em github.com/new cria o repo VAZIO "pilotgram" (sem README).
# 2) Corre (ajusta utilizador se não for DiegoGaviao):
#    GIT_REMOTE=https://github.com/DiegoGaviao/pilotgram.git ./scripts/push_sem_gh.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE="${GIT_REMOTE:-}"

if [[ -z "${REMOTE}" ]]; then
  echo "Define o URL do repo vazio que criaste no GitHub, por exemplo:"
  echo "  GIT_REMOTE=https://github.com/DiegoGaviao/pilotgram.git ./scripts/push_sem_gh.sh"
  exit 1
fi

if [[ ! -d .git ]]; then
  git init
fi

if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add .
  git commit -m "chore: initial Pilotgram (FastAPI + Vite, repo próprio)"
fi
git branch -M main

if git remote get-url origin >/dev/null 2>&1; then
  echo "origin já existe: $(git remote get-url origin)"
else
  git remote add origin "${REMOTE}"
fi

git push -u origin main
echo "Feito. Abre o repo no GitHub e confirma os ficheiros."
