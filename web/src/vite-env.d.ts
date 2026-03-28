/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Pilotgram — preferido */
  readonly VITE_PG_API_URL: string;
  readonly VITE_PG_SUPABASE_URL: string;
  readonly VITE_PG_SUPABASE_ANON_KEY: string;
  /** Legado */
  readonly VITE_API_URL: string;
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
