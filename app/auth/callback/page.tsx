'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LoaderCircle, Play } from 'lucide-react';
import { getSupabaseBrowserClient } from '../../../lib/supabase-browser';

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState('');

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client) { setError('Supabase não configurado.'); return; }
    const code = new URLSearchParams(window.location.search).get('code');
    if (!code) { setError('Código de autorização ausente.'); return; }
    client.auth.exchangeCodeForSession(code).then(({ error: exchangeError }) => {
      if (exchangeError) { setError(exchangeError.message); return; }
      router.replace('/studio?youtube=connected');
    });
  }, [router]);

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#05050a', color: '#fff' }}>
      <div style={{ textAlign: 'center', color: '#aaa6b5' }}>
        <Play size={28} fill="currentColor" color="#c35aff" />
        {error ? <p style={{ color: '#ff879b' }}>{error}</p> : <p style={{ display: 'flex', alignItems: 'center', gap: 8 }}><LoaderCircle className="spin" size={16} /> Finalizando conexão com o YouTube…</p>}
      </div>
    </main>
  );
}
