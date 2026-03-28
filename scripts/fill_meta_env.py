#!/usr/bin/env python3
"""
Copia backend/.env.example → backend/.env e preenche META_APP_ID / META_APP_SECRET
a partir de 06_PROJETOS_ATIVOS/API_KEYS_INVENTORY.md (seção Leads AI), se ainda estiverem vazios.
Não imprime segredos.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
EXAMPLE = BACKEND / ".env.example"
TARGET = BACKEND / ".env"
INVENTORY = ROOT.parent / "API_KEYS_INVENTORY.md"


def _extract_from_inventory(text: str) -> tuple[str | None, str | None]:
    app_id = None
    secret = None
    m_id = re.search(
        r'`META_APP_ID`:\s*`"(\d+)"`',
        text,
    )
    if m_id:
        app_id = m_id.group(1)
    m_sec = re.search(
        r'`META_APP_SECRET`:\s*`"([a-fA-F0-9]+)"`',
        text,
    )
    if m_sec:
        secret = m_sec.group(1)
    return app_id, secret


def main() -> None:
    if not EXAMPLE.is_file():
        raise SystemExit(f"Missing {EXAMPLE}")

    body = EXAMPLE.read_text(encoding="utf-8")
    if INVENTORY.is_file():
        inv = INVENTORY.read_text(encoding="utf-8")
        app_id, secret = _extract_from_inventory(inv)
        if app_id:
            body = re.sub(
                r"^META_APP_ID=.*$",
                f"META_APP_ID={app_id}",
                body,
                flags=re.MULTILINE,
            )
        if secret:
            body = re.sub(
                r"^META_APP_SECRET=.*$",
                f"META_APP_SECRET={secret}",
                body,
                flags=re.MULTILINE,
            )

    TARGET.write_text(body, encoding="utf-8")
    print(f"Wrote {TARGET} (from example + inventory if found)")


if __name__ == "__main__":
    main()
