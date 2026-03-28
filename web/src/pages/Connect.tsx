import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const STATE_KEY = "pilotgram_oauth_state";

type Session = {
  connected: boolean;
  token_preview?: string | null;
  updated_at?: string | null;
};

export default function Connect() {
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const s = await api<Session>("/api/v1/meta/session");
        setSession(s);
      } catch {
        setSession({ connected: false });
      }
    })();
  }, []);

  async function disconnect() {
    setErr(null);
    try {
      await api("/api/v1/meta/session/disconnect", { method: "POST" });
      setSession({ connected: false });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function startOAuth() {
    setErr(null);
    setLoading(true);
    try {
      const { url, state } = await api<{ url: string; state: string }>(
        "/api/v1/meta/oauth/authorize-url"
      );
      sessionStorage.setItem(STATE_KEY, state);
      window.location.href = url;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Conectar Meta</h1>
      {session?.connected && (
        <div className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200">
          <p>
            Sessão ativa (token salvo no SQLite do backend). Última atualização:{" "}
            <span className="text-emerald-100">{session.updated_at ?? "—"}</span>
          </p>
          <p className="mt-1 text-xs text-emerald-400/90">{session.token_preview}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Link
              to="/dashboard"
              className="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-600"
            >
              Ver páginas e posts
            </Link>
            <button
              type="button"
              onClick={() => void disconnect()}
              className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
            >
              Desconectar (apaga token local)
            </button>
          </div>
        </div>
      )}
      <p className="text-sm text-slate-400">
        Você será redirecionado para o Facebook para autorizar o app. É necessário um app configurado
        em developers.facebook.com o redirect tem de ser o mesmo que{" "}
        <code className="text-slate-300">META_OAUTH_REDIRECT_URI</code> no backend:{" "}
        <code className="text-slate-300">https://www.dhawk.com.br/projetos/Pilotgram/oauth/callback</code>
        .
      </p>
      <button
        type="button"
        onClick={() => void startOAuth()}
        disabled={loading}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {loading ? "Abrindo…" : session?.connected ? "Reconectar / trocar conta" : "Entrar com Meta / Facebook"}
      </button>
      {err && <p className="text-sm text-red-400">{err}</p>}
    </div>
  );
}
