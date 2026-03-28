import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";

const STATE_KEY = "pilotgram_oauth_state";

export default function OAuthCallback() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [msg, setMsg] = useState("Trocando código por sessão…");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state") ?? sessionStorage.getItem(STATE_KEY);
    if (!code) {
      setErr("Parâmetro code ausente na URL.");
      return;
    }
    void (async () => {
      try {
        const saved = sessionStorage.getItem(STATE_KEY);
        if (params.get("state") && saved && params.get("state") !== saved) {
          setErr("state OAuth não confere.");
          return;
        }
        await api("/api/v1/meta/oauth/exchange", {
          method: "POST",
          body: JSON.stringify({ code, state: state ?? undefined }),
        });
        sessionStorage.removeItem(STATE_KEY);
        setMsg("Conectado. Redirecionando…");
        setTimeout(() => nav("/dashboard"), 800);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [params, nav]);

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-medium text-white">Callback OAuth</h1>
      {err ? (
        <p className="text-red-400">{err}</p>
      ) : (
        <p className="text-slate-400">{msg}</p>
      )}
      <Link to="/dashboard" className="text-sm text-emerald-400 hover:underline">
        Ir para perfis & mídias
      </Link>
    </div>
  );
}
