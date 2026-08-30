'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { ArrowRight, Check, LockKeyhole, Mail, Play, ShieldCheck } from 'lucide-react';
import { getSupabaseBrowserClient } from '../../lib/supabase-browser';
import '../auth.css';

export default function LoginPage() {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    const supabase = getSupabaseBrowserClient();
    if (!supabase) { setError('Autenticação ainda não está configurada neste ambiente.'); setBusy(false); return; }
    const { error: authError } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    if (authError) { setError('E-mail ou senha inválidos. Confira os dados e tente novamente.'); setBusy(false); return; }
    window.location.assign(new URLSearchParams(window.location.search).get('next') || '/studio');
  }
  return <main className="auth-shell"><div className="auth-glow" /><section className="auth-card">
    <Link className="auth-brand" href="/"><span><Play size={13} fill="currentColor" /></span><strong>NixClip</strong></Link>
    <div className="auth-heading"><span className="auth-kicker">Seu espaço de criação</span><h1>Volte para seus projetos.</h1><p>Entre para continuar de onde parou — seus arquivos e cortes ficam sempre vinculados à sua conta.</p></div>
    <form onSubmit={submit} className="auth-form"><label><span>E-mail</span><div><Mail size={17} /><input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="voce@exemplo.com" /></div></label><label><span>Senha</span><div><LockKeyhole size={17} /><input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="Sua senha" /></div></label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" disabled={busy}>{busy ? 'Entrando…' : 'Entrar no NixClip'} <ArrowRight size={17} /></button></form>
    <div className="auth-trust"><span><ShieldCheck size={15} /> Sessão protegida</span><span><Check size={15} /> Seus projetos são privados</span></div><p className="auth-switch">Ainda não tem uma conta? <Link href="/signup">Criar conta grátis</Link></p>
  </section></main>;
}
