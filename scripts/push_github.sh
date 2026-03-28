#!/usr/bin/env bash
# Cria o repo na conta com que fizeste `gh auth login` e faz o primeiro push.
# O Cursor não tem acesso à tua GitHub — corre no Terminal do Mac.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NAME="${GITHUB_REPO_NAME:-pilotgram}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Não encontrei o comando 'gh' (GitHub CLI)."
  echo ""
  echo "Opção A — instalar e voltar a correr este script:"
  echo "  brew install gh"
  echo "  gh auth login"
  echo "  ./scripts/push_github.sh"
  echo ""
  echo "Opção B — sem instalar nada: cria em github.com/new um repo VAZIO 'pilotgram', depois:"
  echo "  GIT_REMOTE=https://github.com/TEU_USER/pilotgram.git ./scripts/push_sem_gh.sh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Faz login na tua conta: gh auth login"
  exit 1
fi

LOGIN="$(gh api user -q .login)"
FULL="https://github.com/${LOGIN}/${NAME}"

if [[ ! -d .git ]]; then
  git init
fi

if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add .
  git commit -m "chore: initial Pilotgram (FastAPI + Vite, repo próprio)"
fi
git branch -M main

if git remote get-url origin >/dev/null 2>&1; then
  echo "origin já existe. A fazer push para $(git remote get-url origin)"
  git push -u origin main
else
  echo "A criar ${FULL} (privado) e a fazer push..."
  if gh repo view "${LOGIN}/${NAME}" >/dev/null 2>&1; then
    echo "O repo ${NAME} já existe no GitHub. A ligar origin e a fazer push..."
    git remote add origin "https://github.com/${LOGIN}/${NAME}.git"
    git push -u origin main
  else
    gh repo create "${NAME}" --private --source=. --remote=origin --push
  fi
fi

echo "Feito: ${FULL}"
