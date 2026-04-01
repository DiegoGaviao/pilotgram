let base =
  import.meta.env.VITE_PG_API_URL?.trim() ||
  import.meta.env.VITE_API_URL?.trim() ||
  "";
// Só em `vite dev` (local) — em produção tens de preencher VITE_PG_API_URL antes do build.
if (!base && import.meta.env.DEV) {
  base = "http://127.0.0.1:8765";
}

/** Base URL da API (para montar <img src> em URLs absolutas iguais ao fetch). */
export const apiBase = base;

/** URL do preview SVG na API (token opaco). Usa VITE_PG_API_URL quando o JSON veio sem creative_image_url. */
export function creativePreviewUrl(
  imageUrl: string | null | undefined,
  token: string | null | undefined
): string {
  const u = (imageUrl ?? "").trim();
  if (u) return u;
  const t = (token ?? "").trim();
  if (!t || !base) return "";
  return `${base.replace(/\/$/, "")}/api/v1/meta/creatives/${encodeURIComponent(t)}`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  if (!base) {
    throw new Error(
      "Pilotgram: define VITE_PG_API_URL no web/.env (URL HTTPS da API FastAPI em produção)."
    );
  }
  // Não enviar Content-Type em GET/HEAD: vira pedido “não simples”, dispara preflight OPTIONS
  // e alguns proxies (Render/Cloudflare) falham sem cabeçalhos CORS — o Chrome mostra “CORS” genérico.
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers ?? undefined);
  if (method !== "GET" && method !== "HEAD" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const r = await fetch(`${base}${path}`, {
    ...init,
    headers,
    credentials: "omit",
    // Evita respostas antigas do questionário / brief em cache do browser ou CDN intermédia.
    cache: init?.cache ?? "no-store",
  });
  if (!r.ok) {
    const text = await r.text();
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") throw new Error(`${r.status}: ${j.detail}`);
    } catch (e) {
      if (e instanceof Error && e.message.startsWith(`${r.status}:`)) throw e;
    }
    throw new Error(`${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}
