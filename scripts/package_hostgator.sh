#!/usr/bin/env bash
# Build do front + ZIP para cPanel Hostgator.
# Saída: 06_PROJETOS_ATIVOS/09_PILOTGRAM_DEPLOY/pilotgram_cpanel_<data>.zip
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJETOS_ATIVOS="$(cd "$PG_ROOT/.." && pwd)"
OUT_DIR="$PROJETOS_ATIVOS/09_PILOTGRAM_DEPLOY"
STAMP="$(date +%Y%m%d_%H%M)"
ZIP_NAME="pilotgram_cpanel_${STAMP}.zip"
ZIP_PATH="$OUT_DIR/$ZIP_NAME"

mkdir -p "$OUT_DIR"

echo ">>> Pilotgram root: $PG_ROOT"
echo ">>> ZIP destino:    $ZIP_PATH"
echo ""

if [[ ! -f "$PG_ROOT/web/package.json" ]]; then
  echo "Erro: não encontrei web/package.json em $PG_ROOT"
  exit 1
fi

cd "$PG_ROOT/web"
npm install
npm run build

if [[ ! -d dist ]] || [[ ! -f dist/index.html ]]; then
  echo "Erro: build não gerou web/dist/index.html"
  exit 1
fi

# Raiz do ZIP = raiz do dist: index.html, .htaccess, assets/ (JS/CSS lá dentro)
(cd dist && zip -q -r "$ZIP_PATH" .)
# Guia de extração dentro do ZIP (cPanel costuma criar subpasta — o texto explica)
zip -qj "$ZIP_PATH" "$SCRIPT_DIR/LEIA_ME_CPANEL_EXTRACAO.txt"

echo ""
echo "OK — ZIP pronto para o cPanel:"
echo "  $ZIP_PATH"
echo ""
echo "No servidor: pasta projetos/pilotgram (ex.: ~/dhawk.com.br/projetos/pilotgram)"
echo "  → extrair o ZIP AQUI. A raiz do ZIP deve coincidir com a raiz de pilotgram."
echo "  Ver lista:"
unzip -l "$ZIP_PATH" | head -25
