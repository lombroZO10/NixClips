import { redirect } from 'next/navigation';
import { getSupabaseServerClient } from '../../lib/supabase-server';

export default async function StudioLayout({ children }: { children: React.ReactNode }) {
  const supabase = await getSupabaseServerClient();
  if (!supabase) redirect('/login?next=/studio');
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/login?next=/studio');
  return children;
}
