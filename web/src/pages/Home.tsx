import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Pilotgram</h1>
      <p className="text-slate-400 leading-relaxed">
        Planeamento e publicação no Instagram com <strong className="text-slate-200">Meta (Facebook Login)</strong>
        , conta <strong className="text-slate-200">Criador</strong> ou{" "}
        <strong className="text-slate-200">Empresa</strong>, dados na{" "}
        <strong className="text-slate-200">Supabase</strong> em produção e API{" "}
        <strong className="text-slate-200">FastAPI</strong> (VPS Hostinger, Render, etc.). Próximo: LLM
        estilo Leads AI, aprovação e agendamento.
      </p>
      <Link
        to="/connect"
        className="inline-flex rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
      >
        Conectar Meta
      </Link>
      <p className="text-xs text-slate-500">
        Produção: <code className="text-slate-400">dhawk.com.br/projetos/pilotgram/</code> — ver{" "}
        <code className="text-slate-400">DEPLOY_DHAWK.md</code> e <code className="text-slate-400">PREREQUISITES.md</code>.
      </p>
    </div>
  );
}
