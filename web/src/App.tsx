import { Routes, Route, Link, NavLink } from "react-router-dom";
import Home from "./pages/Home";
import Connect from "./pages/Connect";
import OAuthCallback from "./pages/OAuthCallback";
import Dashboard from "./pages/Dashboard";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-semibold text-emerald-400">
            Pilotgram
          </Link>
          <nav className="flex gap-3 text-sm">
            <NavLink
              to="/connect"
              className={({ isActive }) =>
                isActive ? "text-white" : "text-slate-400 hover:text-slate-200"
              }
            >
              Conectar Meta
            </NavLink>
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                isActive ? "text-white" : "text-slate-400 hover:text-slate-200"
              }
            >
              Perfis & mídias
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/connect" element={<Connect />} />
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  );
}
