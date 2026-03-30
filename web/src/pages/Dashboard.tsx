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
type SuggestionRow = {
  id: number;
  ig_user_id: string;
  source_media_id?: string | null;
  suggestion_text: string;
  rationale?: string | null;
  status: string;
  created_at: string;
  approved_at?: string | null;
  creative_prompt?: string | null;
  creative_image_url?: string | null;
  suggested_date?: string | null;
  frequency_per_week?: number | null;
  focus_topic?: string | null;
  language?: string | null;
};
type ProfileDna = {
  ig_user_id: string;
  themes: string[];
  tone_hint: string;
  cta_hint: string;
  updated_at: string;
};
type ProfileBrief = {
  ig_user_id: string;
  niche: string;
  target_audience: string;
  objective: string;
  offer_summary: string;
  preferred_language: string;
  tone_style: string;
  do_not_use_terms: string;
  updated_at: string;
};

export default function Dashboard() {
  const [pages, setPages] = useState<PageIg[] | null>(null);
  const [selectedIg, setSelectedIg] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaRow[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestionRow[]>([]);
  const [dna, setDna] = useState<ProfileDna | null>(null);
  const [brief, setBrief] = useState<ProfileBrief | null>(null);
  const [focusTopic, setFocusTopic] = useState("autoajuda, coaching, desenvolvimento pessoal");
  const [frequencyPerWeek, setFrequencyPerWeek] = useState(3);
  const [generating, setGenerating] = useState(false);
  const [savingBrief, setSavingBrief] = useState(false);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [brokenImages, setBrokenImages] = useState<Record<number, true>>({});
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
      setSuggestions([]);
      setDna(null);
      return;
    }
    void (async () => {
      try {
        const [res, sres, dres, bres] = await Promise.all([
          api<{ data: MediaRow[] }>(`/api/v1/meta/ig/${selectedIg}/media-with-insights?limit=8`),
          api<{ data: SuggestionRow[] }>(`/api/v1/meta/ig/${selectedIg}/suggestions`),
          api<ProfileDna>(`/api/v1/meta/ig/${selectedIg}/dna`).catch(() => null),
          api<ProfileBrief>(`/api/v1/meta/ig/${selectedIg}/brief`).catch(() => null),
        ]);
        setMedia(res.data);
        setSuggestions(sres.data);
        setDna(dres);
        setBrief(
          bres ?? {
            ig_user_id: selectedIg,
            niche: "",
            target_audience: "",
            objective: "",
            offer_summary: "",
            preferred_language: "",
            tone_style: "",
            do_not_use_terms: "",
            updated_at: "",
          }
        );
        setErr(null);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
        setMedia([]);
        setSuggestions([]);
        setDna(null);
        setBrief(null);
      }
    })();
  }, [selectedIg]);

  async function generateSuggestions() {
    if (!selectedIg) return;
    setGenerating(true);
    setErr(null);
    try {
      const res = await api<{ data: SuggestionRow[] }>(
        `/api/v1/meta/ig/${selectedIg}/suggestions/generate?count=5&frequency_per_week=${frequencyPerWeek}&focus_topic=${encodeURIComponent(
          focusTopic
        )}`,
        { method: "POST" }
      );
      // Mostra só o lote recém-gerado para evitar sensação de duplicação.
      setSuggestions(res.data);
      const dres = await api<ProfileDna>(`/api/v1/meta/ig/${selectedIg}/dna`).catch(() => null);
      setDna(dres);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function saveBrief() {
    if (!selectedIg || !brief) return;
    setSavingBrief(true);
    setErr(null);
    try {
      const saved = await api<ProfileBrief>(`/api/v1/meta/ig/${selectedIg}/brief`, {
        method: "PUT",
        body: JSON.stringify({
          niche: brief.niche,
          target_audience: brief.target_audience,
          objective: brief.objective,
          offer_summary: brief.offer_summary,
          preferred_language: brief.preferred_language,
          tone_style: brief.tone_style,
          do_not_use_terms: brief.do_not_use_terms,
        }),
      });
      setBrief(saved);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingBrief(false);
    }
  }

  async function approveSuggestion(id: number) {
    setApprovingId(id);
    setErr(null);
    try {
      const row = await api<SuggestionRow>(`/api/v1/meta/suggestions/${id}/approve`, {
        method: "POST",
      });
      setSuggestions((prev) => prev.map((s) => (s.id === id ? row : s)));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setApprovingId(null);
    }
  }

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
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-medium text-slate-200">Sugestões dos robôs (MVP)</h2>
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={focusTopic}
                onChange={(e) => setFocusTopic(e.target.value)}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                placeholder="Foco do perfil"
              />
              <select
                value={frequencyPerWeek}
                onChange={(e) => setFrequencyPerWeek(Number(e.target.value))}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              >
                <option value={2}>2x/semana</option>
                <option value={3}>3x/semana</option>
                <option value={4}>4x/semana</option>
                <option value={5}>5x/semana</option>
              </select>
              <button
                type="button"
                onClick={() => void generateSuggestions()}
                disabled={generating}
                className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {generating ? "Gerando..." : "Gerar sugestões IA"}
              </button>
            </div>
          </div>
          {dna && (
            <div className="rounded-md border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-300">
              <p className="font-medium text-slate-200">DNA do perfil</p>
              <p className="mt-1">Temas: {dna.themes.length ? dna.themes.join(", ") : "—"}</p>
              <p className="mt-1">{dna.tone_hint}</p>
              <p className="mt-1">{dna.cta_hint}</p>
            </div>
          )}
          {brief && (
            <div className="rounded-md border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-300">
              <p className="mb-2 font-medium text-slate-200">Questionário estratégico da página</p>
              <div className="grid gap-2 md:grid-cols-2">
                <input
                  value={brief.niche}
                  onChange={(e) => setBrief({ ...brief, niche: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Nicho (ex: liderança para empreendedoras)"
                />
                <input
                  value={brief.target_audience}
                  onChange={(e) => setBrief({ ...brief, target_audience: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Público-alvo"
                />
                <input
                  value={brief.objective}
                  onChange={(e) => setBrief({ ...brief, objective: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Objetivo principal"
                />
                <input
                  value={brief.offer_summary}
                  onChange={(e) => setBrief({ ...brief, offer_summary: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Oferta/serviço"
                />
                <input
                  value={brief.preferred_language}
                  onChange={(e) => setBrief({ ...brief, preferred_language: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Idioma preferido (en ou pt)"
                />
                <input
                  value={brief.tone_style}
                  onChange={(e) => setBrief({ ...brief, tone_style: e.target.value })}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Tom (ex: direto, premium, acolhedor)"
                />
              </div>
              <input
                value={brief.do_not_use_terms}
                onChange={(e) => setBrief({ ...brief, do_not_use_terms: e.target.value })}
                className="mt-2 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                placeholder="Termos proibidos (separados por vírgula)"
              />
              <button
                type="button"
                onClick={() => void saveBrief()}
                disabled={savingBrief}
                className="mt-2 rounded bg-blue-700 px-3 py-1 text-xs font-medium text-white hover:bg-blue-600 disabled:opacity-50"
              >
                {savingBrief ? "Salvando..." : "Salvar questionário"}
              </button>
            </div>
          )}
          {suggestions.length ? (
            <ul className="space-y-3">
              {suggestions.map((s) => (
                <li
                  key={s.id}
                  className="rounded-md border border-slate-800 bg-slate-900/40 p-3 text-sm"
                >
                  <p className="text-xs text-slate-500">
                    gerado: {s.created_at} {s.suggested_date ? `· sugerido: ${s.suggested_date}` : ""}
                  </p>
                  <div className="mt-2 overflow-hidden rounded-xl border border-slate-700 bg-black">
                    <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2 text-xs text-slate-300">
                      <span>@preview_instagram</span>
                      <span>
                        {s.frequency_per_week ? `${s.frequency_per_week}x/semana` : ""}
                        {s.language ? ` · ${s.language.toUpperCase()}` : ""}
                      </span>
                    </div>
                    <div className="aspect-square bg-slate-950">
                      {s.creative_image_url && !brokenImages[s.id] ? (
                        <img
                          src={s.creative_image_url}
                          alt="Criativo sugerido"
                          className="h-full w-full object-cover"
                          loading="lazy"
                          referrerPolicy="no-referrer"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                            setBrokenImages((prev) => ({ ...prev, [s.id]: true }));
                          }}
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 text-center text-xs text-slate-300">
                          Preview criativo indisponivel no host
                        </div>
                      )}
                    </div>
                    <div className="space-y-2 px-3 py-3">
                      <p className="text-xs text-slate-400">{s.focus_topic || "foco do perfil"}</p>
                      <p className="text-xs font-medium text-emerald-300">Legenda pronta (copiar e postar):</p>
                      <p className="whitespace-pre-wrap text-slate-200">{s.suggestion_text}</p>
                    </div>
                  </div>
                  {s.rationale && <p className="mt-2 text-xs text-slate-500">{s.rationale}</p>}
                  {s.creative_prompt && (
                    <p className="mt-2 text-xs text-slate-500">criativo: {s.creative_prompt}</p>
                  )}
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-slate-500">status: {s.status}</p>
                    {s.status !== "approved" && (
                      <button
                        type="button"
                        onClick={() => void approveSuggestion(s.id)}
                        disabled={approvingId === s.id}
                        className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                      >
                        {approvingId === s.id ? "Aprovando..." : "Aprovar"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">
              Ainda sem sugestões. Clique em "Gerar sugestões IA" para criar os primeiros rascunhos.
            </p>
          )}

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
