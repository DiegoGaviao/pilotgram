import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type PageIg = {
  page_id: string;
  page_name: string;
  ig_user_id: string | null;
  ig_username: string | null;
};

type MediaRow = Record<string, unknown> & { id?: string; caption?: string };

export default function Dashboard() {
  const [pages, setPages] = useState<PageIg[] | null>(null);
  const [selectedIg, setSelectedIg] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const list = await api<PageIg[]>("/api/v1/meta/pages");
        setPages(list);
        const firstIg = list.find((p) => p.ig_user_id)?.ig_user_id;
        if (firstIg) setSelectedIg(firstIg);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  useEffect(() => {
    if (!selectedIg) {
      setMedia([]);
      return;
    }
    void (async () => {
      try {
        const res = await api<{ data: MediaRow[] }>(
          `/api/v1/meta/ig/${selectedIg}/media-with-insights?limit=8`
        );
        setMedia(res.data);
        setErr(null);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
        setMedia([]);
      }
    })();
  }, [selectedIg]);

  if (err && !pages) {
    return (
      <div className="space-y-3">
        <p className="text-red-400">{err}</p>
        <Link to="/connect" className="text-emerald-400 hover:underline">
          Conectar Meta
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Páginas e Instagram</h1>
      {!pages?.length ? (
        <p className="text-slate-400">Nenhuma página retornada (ou ainda carregando).</p>
      ) : (
        <ul className="space-y-2">
          {pages.map((p) => (
            <li
              key={p.page_id}
              className={`rounded-lg border px-3 py-2 text-sm ${
                p.ig_user_id && selectedIg === p.ig_user_id
                  ? "border-emerald-600 bg-emerald-950/40"
                  : "border-slate-800 bg-slate-900/50"
              }`}
            >
              <div className="font-medium text-slate-200">{p.page_name}</div>
              {p.ig_user_id ? (
                <button
                  type="button"
                  onClick={() => setSelectedIg(p.ig_user_id)}
                  className="mt-1 text-left text-xs text-slate-400 hover:text-emerald-400"
                >
                  @{p.ig_username ?? p.ig_user_id} — clique para ver mídias
                </button>
              ) : (
                <p className="mt-1 text-xs text-amber-600/90">
                  Sem Instagram Business ligado a esta Página.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {selectedIg && (
        <section className="space-y-2">
          <h2 className="text-lg font-medium text-slate-200">Amostra de posts (API)</h2>
          {err && <p className="text-xs text-amber-500">{err}</p>}
          <ul className="space-y-3">
            {media.map((m, idx) => (
              <li
                key={String(m.id ?? idx)}
                className="rounded-md border border-slate-800 bg-slate-900/40 p-3 text-sm"
              >
                <p className="text-xs text-slate-500">{String(m.timestamp ?? "")}</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-300">
                  {(m.caption as string)?.slice(0, 280) || "(sem legenda)"}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  likes {String(m.like_count ?? "—")} · comentários{" "}
                  {String(m.comments_count ?? "—")}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-slate-600">
        Próximo: snapshots no Postgres (Supabase), LLM, roteiros estilo Leads AI, fila de publicação.
      </p>
    </div>
  );
}
