import { createBrowserClient } from '@supabase/ssr';

export function getSupabaseBrowserClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return createBrowserClient(url, key);
}

export async function connectYouTube() {
  const client = getSupabaseBrowserClient();
  if (!client) throw new Error('Configure o Supabase para conectar o YouTube.');
  const redirectTo = `${window.location.origin}/auth/callback`;
  const { error } = await client.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo,
      scopes: 'https://www.googleapis.com/auth/youtube.readonly',
      queryParams: { access_type: 'offline', prompt: 'consent' },
    },
  });
  if (error) throw error;
}
