import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, apiBase, creativePreviewUrl } from "../api";

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
  creative_fetch_token?: string | null;
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
  language_hint?: string;
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
  /** True quando campos vazios foram preenchidos pela análise do DNA (posts). */
  filled_from_dna?: boolean;
};

const BRIEF_LS_PREFIX = "pilotgram.brief.v1.";

function briefLocalKey(ig: string) {
  return `${BRIEF_LS_PREFIX}${ig}`;
}

function normalizePrefLang(s: string): "en" | "pt" | null {
  const x = (s ?? "").trim().toLowerCase().replace(/_/g, "-");
  if (!x) return null;
  if (x === "en" || x === "english" || x.startsWith("en-")) return "en";
  if (x.includes("ingl")) return "en";
  if (x === "pt" || x === "pt-br" || x.startsWith("pt-") || x.includes("portug")) return "pt";
  return null;
}

function mergeBriefWithLocalStorage(ig: string, apiBrief: ProfileBrief): ProfileBrief {
  let merged: ProfileBrief = { ...apiBrief };
  try {
    const raw = localStorage.getItem(briefLocalKey(ig));
    if (!raw) return merged;
    const loc = JSON.parse(raw) as Partial<ProfileBrief>;
    const keys = [
      "niche",
      "target_audience",
      "objective",
      "offer_summary",
      "preferred_language",
      "tone_style",
      "do_not_use_terms",
    ] as const;
    for (const k of keys) {
      const apiEmpty = !(merged[k] ?? "").trim();
      const locVal = (loc[k] ?? "").toString().trim();
      if (apiEmpty && locVal) merged = { ...merged, [k]: locVal };
    }
    // Idioma: o servidor manda (PUT gravou). Só usamos o local se a API não trouxe pt/en (ex.: rascunho offline).
    const locLang = normalizePrefLang((loc.preferred_language ?? "").toString());
    const apiLang = normalizePrefLang(merged.preferred_language);
    if (locLang && !apiLang) {
      merged = { ...merged, preferred_language: locLang };
    }
  } catch {
    /* ignore */
  }
  return merged;
}

function persistBriefLocal(ig: string, b: ProfileBrief) {
  try {
    const payload = {
      niche: b.niche,
      target_audience: b.target_audience,
      objective: b.objective,
      offer_summary: b.offer_summary,
      preferred_language: b.preferred_language,
      tone_style: b.tone_style,
      do_not_use_terms: b.do_not_use_terms,
      /** ISO do último GET/PUT — evita drift com cópia antiga no browser */
      brief_server_updated_at: b.updated_at ?? "",
    };
    localStorage.setItem(briefLocalKey(ig), JSON.stringify(payload));
  } catch {
    /* ignore */
  }
}

function briefAllFieldsEmpty(b: ProfileBrief): boolean {
  return ![
    b.niche,
    b.target_audience,
    b.objective,
    b.offer_summary,
    b.preferred_language,
    b.tone_style,
    b.do_not_use_terms,
  ].some((x) => (x ?? "").trim());
}

const BRIEF_HELP: Record<string, string> = {
  niche:
    "Em uma frase: que mercado ou tema você domina? Quanto mais específico, melhor o robô acerta. Ex.: “liderança para mães empreendedoras”, “gelo escultural para casamentos”. Evite só “motivação” ou “conteúdo”.",
  target_audience:
    "Quem é a pessoa que você quer atrair: faixa etária, contexto de vida, principal dor ou desejo. Ex.: “mulheres 30–45, culpa e cansaço ao conciliar filhos e negócio”.",
  objective:
    "Meta clara para 60–90 dias no Instagram: vender mentoria, gerar leads no WhatsApp, crescer alcance, posicionar autoridade. Uma linha já basta.",
  offer_summary:
    "O que você vende ou quer vender (nome + formato). Ex.: “mentoria 12 semanas”, “consultoria de anúncios”, “ebook + comunidade”. Ajuda a amarrar CTA e criativos.",
  preferred_language:
    "Escolha o idioma das legendas. English força inglês mesmo se os posts forem em português. Auto usa o DNA e, se preciso, detecta pelas legendas.",
  tone_style:
    "Como você fala na marca: 2–5 palavras. Ex.: “acolhedor e direto”, “técnico sem jargão”, “provocador com humor leve”, “premium e calmo”.",
  do_not_use_terms:
    "Lista separada por vírgula: palavras proibidas (concorrentes, promessas arriscadas, gírias que você evita). O gerador tenta remover esses termos do texto.",
};

/** Carrega criativo cross-origin via fetch→blob para contornar CSP do Hostgator em img-src. */
function SuggestionCreativeImage({
  suggestionId,
  imageUrl,
  token,
}: {
  suggestionId: number;
  imageUrl?: string | null;
  token?: string | null;
}) {
  const resolved = creativePreviewUrl(imageUrl, token);
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    setSrc(null);
    if (!resolved) {
      setFailed(true);
      return;
    }
    let alive = true;
    let blobUrl: string | null = null;
    let cross = false;
    try {
      cross = new URL(resolved).origin !== window.location.origin;
    } catch {
      cross = false;
    }
    if (!cross) {
      setSrc(resolved);
      return () => {
        alive = false;
      };
    }
    void (async () => {
      try {
        const r = await fetch(resolved, { mode: "cors", credentials: "omit" });
        if (!r.ok) throw new Error(String(r.status));
        const blob = await r.blob();
        if (!alive) return;
        blobUrl = URL.createObjectURL(blob);
        setSrc(blobUrl);
      } catch {
        if (alive) {
          setSrc(resolved);
        }
      }
    })();
    return () => {
      alive = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [resolved, suggestionId]);

  if (failed || !resolved) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 text-center text-[11px] text-slate-400">
        <span>
          {!apiBase
            ? "Defina VITE_PG_API_URL no build do front (mesma URL da API)."
            : "Não foi possível mostrar o criativo aqui (rede ou bloqueio)."}
        </span>
        {resolved ? (
          <a href={resolved} target="_blank" rel="noreferrer" className="text-emerald-500 hover:underline">
            Abrir criativo numa nova aba
          </a>
        ) : null}
      </div>
    );
  }
  if (!src) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-950 text-[11px] text-slate-500">
        A carregar criativo…
      </div>
    );
  }
  return (
    <img
      src={src}
      alt="Criativo sugerido"
      className="h-full w-full object-cover"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function BriefFieldHelp({ children }: { children: ReactNode }) {
  return (
    <details className="relative inline-block align-middle">
      <summary className="ml-1 inline-flex cursor-pointer list-none items-center justify-center rounded-full border border-slate-600 bg-slate-800/80 px-1.5 py-0.5 text-[10px] font-bold text-slate-400 hover:border-emerald-600 hover:text-emerald-400 [&::-webkit-details-marker]:hidden">
        ?
      </summary>
      <div className="absolute right-0 z-30 mt-1 w-[min(calc(100vw-2rem),18rem)] rounded-md border border-slate-700 bg-slate-950 p-2 text-[11px] leading-snug text-slate-300 shadow-xl">
        {children}
      </div>
    </details>
  );
}

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
  const [err, setErr] = useState<string | null>(null);
  const needsReconnect = !!err && err.startsWith("401:");

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
      setBrief(null);
      return;
    }
    const ig = selectedIg;
    let cancelled = false;

    void (async () => {
      try {
        const [res, sres] = await Promise.all([
          api<{ data: MediaRow[] }>(`/api/v1/meta/ig/${ig}/media-with-insights?limit=8`),
          api<{ data: SuggestionRow[] }>(`/api/v1/meta/ig/${ig}/suggestions`),
        ]);
        if (cancelled) return;
        setMedia(res.data);
        setSuggestions(sres.data);

        let dres = await api<ProfileDna>(`/api/v1/meta/ig/${ig}/dna`).catch(() => null);
        if (cancelled) return;
        if (!dres && res.data.length > 0) {
          dres = await api<ProfileDna>(`/api/v1/meta/ig/${ig}/dna/refresh`, {
            method: "POST",
          }).catch(() => null);
        }
        if (cancelled) return;
        setDna(dres);

        const bres = await api<ProfileBrief>(`/api/v1/meta/ig/${ig}/brief`).catch(() => null);
        if (cancelled) return;
        const baseBrief: ProfileBrief =
          bres ?? {
            ig_user_id: ig,
            niche: "",
            target_audience: "",
            objective: "",
            offer_summary: "",
            preferred_language: "",
            tone_style: "",
            do_not_use_terms: "",
            updated_at: "",
            filled_from_dna: false,
          };
        const mergedBrief = mergeBriefWithLocalStorage(ig, baseBrief);
        setBrief(mergedBrief);
        persistBriefLocal(ig, mergedBrief);
        setErr(null);
      } catch (e) {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
        setMedia([]);
        setSuggestions([]);
        setDna(null);
        setBrief(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedIg]);

  async function generateSuggestions() {
    if (!selectedIg) return;
    setGenerating(true);
    setErr(null);
    try {
      if (brief) {
        const savedBrief = await api<ProfileBrief>(`/api/v1/meta/ig/${selectedIg}/brief`, {
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
        const mergedAfterPut = mergeBriefWithLocalStorage(selectedIg, savedBrief);
        setBrief(mergedAfterPut);
        persistBriefLocal(selectedIg, mergedAfterPut);
      }
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
      const b2 = await api<ProfileBrief>(`/api/v1/meta/ig/${selectedIg}/brief`).catch(() => null);
      if (b2) {
        const merged = mergeBriefWithLocalStorage(selectedIg, b2);
        setBrief(merged);
        persistBriefLocal(selectedIg, merged);
      }
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
      const mergedSaved = mergeBriefWithLocalStorage(selectedIg, saved);
      setBrief(mergedSaved);
      persistBriefLocal(selectedIg, mergedSaved);
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
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <p className="font-medium text-slate-200">Questionário estratégico da página</p>
                <details className="text-[11px] text-slate-500">
                  <summary className="cursor-pointer list-none text-emerald-500/90 hover:underline [&::-webkit-details-marker]:hidden">
                    Resumo: como responder
                  </summary>
                  <p className="mt-2 max-w-xl rounded border border-slate-800 bg-slate-950/80 p-2 text-slate-400">
                    Quanto mais concreto, melhor a legenda e o criativo. O sistema cruza estas respostas com o{" "}
                    <strong className="text-slate-300">DNA</strong> (temas e padrões extraídos dos seus posts
                    recentes). Campos vazios podem ser sugeridos automaticamente a partir do Instagram — revise
                    sempre. Use <strong className="text-slate-300">Atualizar questionário</strong> para gravar no
                    servidor; ao <strong className="text-slate-300">Gerar sugestões</strong>, o que está no
                    formulário é salvo antes de gerar.
                  </p>
                </details>
              </div>
              {brief.updated_at ? (
                <p className="mb-2 text-[11px] text-slate-500">
                  Última gravação no servidor: {brief.updated_at}
                </p>
              ) : null}
              {brief.updated_at && briefAllFieldsEmpty(brief) ? (
                <p className="mb-2 text-[11px] text-sky-500/95">
                  A última gravação tinha todos os campos vazios (ou o servidor foi reiniciado e perdeu dados
                  antigos). Preencha abaixo ou confira as sugestões vindas do DNA após carregar os posts.
                </p>
              ) : null}
              {brief.filled_from_dna ? (
                <p className="mb-2 text-[11px] text-amber-500/95">
                  Parte do texto veio da análise automática dos posts (DNA). Revise e use &quot;Atualizar
                  questionário&quot; para gravar no servidor, ou gere sugestões — o que está no formulário é o que
                  será usado ao gerar.
                </p>
              ) : null}
              <div className="grid gap-3 md:grid-cols-2">
                {(
                  [
                    ["niche", "Nicho", "Nicho (ex: liderança para empreendedoras)"],
                    ["target_audience", "Público-alvo", "Quem você quer atingir"],
                    ["objective", "Objetivo principal", "Meta nos próximos 60–90 dias"],
                    ["offer_summary", "Oferta / serviço", "O que você vende ou oferece"],
                    ["preferred_language", "Idioma das legendas", ""],
                    ["tone_style", "Tom de voz", "Ex.: acolhedor, direto, premium"],
                  ] as const
                ).map(([key, label, ph]) => (
                  <div key={key} className="flex flex-col gap-1">
                    <div className="flex items-center">
                      <span className="text-[11px] font-medium text-slate-400">{label}</span>
                      <BriefFieldHelp>{BRIEF_HELP[key]}</BriefFieldHelp>
                    </div>
                    {key === "preferred_language" ? (
                      <select
                        value={
                          normalizePrefLang(brief.preferred_language) ?? ""
                        }
                        onChange={(e) =>
                          setBrief({
                            ...brief,
                            preferred_language: e.target.value,
                          } as ProfileBrief)
                        }
                        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                      >
                        <option value="">Auto (DNA / detectar dos posts)</option>
                        <option value="pt">Português</option>
                        <option value="en">English</option>
                      </select>
                    ) : (
                      <input
                        value={brief[key]}
                        onChange={(e) =>
                          setBrief({ ...brief, [key]: e.target.value } as ProfileBrief)
                        }
                        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                        placeholder={ph}
                      />
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-col gap-1">
                <div className="flex items-center">
                  <span className="text-[11px] font-medium text-slate-400">Termos proibidos</span>
                  <BriefFieldHelp>{BRIEF_HELP.do_not_use_terms}</BriefFieldHelp>
                </div>
                <input
                  value={brief.do_not_use_terms}
                  onChange={(e) => setBrief({ ...brief, do_not_use_terms: e.target.value })}
                  className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                  placeholder="Separados por vírgula"
                />
              </div>
              <button
                type="button"
                onClick={() => void saveBrief()}
                disabled={savingBrief}
                className="mt-2 rounded bg-blue-700 px-3 py-1 text-xs font-medium text-white hover:bg-blue-600 disabled:opacity-50"
              >
                {savingBrief ? "Atualizando..." : "Atualizar questionário"}
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
                      <SuggestionCreativeImage
                        suggestionId={s.id}
                        imageUrl={s.creative_image_url}
                        token={s.creative_fetch_token}
                      />
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
          {err && (
            <div className="space-y-1">
              <p className="text-xs text-amber-500">{err}</p>
              {needsReconnect && (
                <Link to="/connect" className="text-xs text-emerald-400 hover:underline">
                  Reconectar Meta agora
                </Link>
              )}
            </div>
          )}
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
