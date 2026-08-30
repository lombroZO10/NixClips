import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '../../../lib/supabase-server';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const next = url.searchParams.get('next');
  const destination = next?.startsWith('/') && !next.startsWith('//') ? next : '/studio';
  const supabase = await getSupabaseServerClient();
  if (supabase && code) await supabase.auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(destination, url.origin));
}
