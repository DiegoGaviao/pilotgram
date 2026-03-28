import { createClient } from "@supabase/supabase-js";

const url =
  import.meta.env.VITE_PG_SUPABASE_URL?.trim() ||
  import.meta.env.VITE_SUPABASE_URL?.trim() ||
  "";
const anon =
  import.meta.env.VITE_PG_SUPABASE_ANON_KEY?.trim() ||
  import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() ||
  "";

/** Cliente anon — PG_* no .env (Vite só expõe variáveis com prefixo VITE_). */
export const supabase = url && anon ? createClient(url, anon) : null;
