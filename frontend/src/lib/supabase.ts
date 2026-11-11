import { createClient } from '@supabase/supabase-js'

/** Supabase client: used only for login and session; all data goes through the API. */
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)
