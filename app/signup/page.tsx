'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { ArrowRight, Check, LockKeyhole, Mail, Play, ShieldCheck, UserRound } from 'lucide-react';
import { getSupabaseBrowserClient } from '../../lib/supabase-browser';
import '../auth.css';

export default function SignupPage() {
  const [name, setName] = useState(''); const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [error, setError] = useState(''); const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); setMessage(''); if (password.length < 8) { setError('Use uma senha com pelo menos 8 caracteres.'); return; } setBusy(true);
    const supabase = getSupabaseBrowserClient(); if (!supabase) { setError('Autenticação ainda não está configurada neste ambiente.'); setBusy(false); return; }
    const { data, error: authError } = await supabase.auth.signUp({ email: email.trim(), password, options: { data: { full_name: name.trim() }, emailRedirectTo: `${window.location.origin}/auth/callback` } });
    if (authError) setError(authError.message.includes('already') ? 'Este e-mail já possui uma conta.' : 'Não foi possível criar sua conta agora.'); else if (data.session) window.location.assign('/studio'); else setMessage('Conta criada. Confira seu e-mail para confirmar o acesso.'); setBusy(false);
  }
  return <main className="auth-shell"><div className="auth-glow" /><section className="auth-card"><Link className="auth-brand" href="/"><span><Play size={13} fill="currentColor" /></span><strong>NixClip</strong></Link><div className="auth-heading"><span className="auth-kicker">Comece sem complicação</span><h1>Seu próximo corte começa aqui.</h1><p>Crie seu espaço pessoal e transforme vídeos longos em histórias que merecem ser vistas.</p></div><form onSubmit={submit} className="auth-form"><label><span>Como podemos chamar você?</span><div><UserRound size={17} /><input autoComplete="name" required value={name} onChange={e => setName(e.target.value)} placeholder="Seu nome" /></div></label><label><span>E-mail</span><div><Mail size={17} /><input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="voce@exemplo.com" /></div></label><label><span>Senha</span><div><LockKeyhole size={17} /><input type="password" autoComplete="new-password" minLength={8} required value={password} onChange={e => setPassword(e.target.value)} placeholder="Mínimo de 8 caracteres" /></div></label>{error && <p className="auth-error" role="alert">{error}</p>}{message && <p className="auth-message" role="status">{message}</p>}<button className="auth-submit" disabled={busy}>{busy ? 'Criando conta…' : 'Criar minha conta'} <ArrowRight size={17} /></button></form><div className="auth-trust"><span><ShieldCheck size={15} /> Dados criptografados</span><span><Check size={15} /> Sem cartão de crédito</span></div><p className="auth-switch">Já tem uma conta? <Link href="/login">Entrar</Link></p></section></main>;
}
