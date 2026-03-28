let base =
  import.meta.env.VITE_PG_API_URL?.trim() ||
  import.meta.env.VITE_API_URL?.trim() ||
  "";
// Só em `vite dev` (local) — em produção tens de preencher VITE_PG_API_URL antes do build.
if (!base && import.meta.env.DEV) {
  base = "http://127.0.0.1:8765";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  if (!base) {
    throw new Error(
      "Pilotgram: define VITE_PG_API_URL no web/.env (URL HTTPS da API FastAPI em produção)."
    );
  }
  const r = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}
