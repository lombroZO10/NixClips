import Link from 'next/link';
import {
  ArrowRight, Captions, Check, Clapperboard, Frame, Link2, Play,
  ScanFace, Sparkles, Upload, WandSparkles,
} from 'lucide-react';
import { getSupabaseServerClient } from '../lib/supabase-server';

const intelligence = [
  { icon: Clapperboard, label: 'Cortes por contexto' },
  { icon: ScanFace, label: 'Tracking inteligente' },
  { icon: Captions, label: 'Legendas dinâmicas' },
  { icon: Frame, label: 'Reframe 9:16' },
];

export default async function Home() {
  const supabase = await getSupabaseServerClient();
  const { data: { user } } = supabase ? await supabase.auth.getUser() : { data: { user: null } };
  return (
    <main className="landing-shell">
      <div className="ambient ambient-violet" /><div className="ambient ambient-red" /><div className="noise" />
      <header className="site-header">
        <Link className="brand" href="/" aria-label="NixClip — início">
          <span className="brand-mark" aria-hidden="true"><span /><Play size={14} fill="currentColor" strokeWidth={0} /></span>
          <span className="brand-name">NixClip</span>
        </Link>
        <nav className="main-nav" aria-label="Navegação principal">
          <a href="#motor">Motor AI</a><a href="#workflow">Workflow</a><a href="#recursos">Recursos</a>
        </nav>
        <div className="header-actions">{user ? <><a className="header-login" href="/auth/signout">Sair</a><a className="header-cta" href="/studio">Abrir Studio <ArrowRight size={16} /></a></> : <><a className="header-login" href="/login">Entrar</a><a className="header-cta" href="/signup">Criar conta grátis <ArrowRight size={16} /></a></>}</div>
      </header>

      <section className="hero-section">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-icon"><Sparkles size={13} /></span> Inteligência de vídeo feita para criadores</div>
          <h1>Um vídeo longo.<span> Cortes que já nascem prontos.</span></h1>
          <p className="hero-lead">O NixClip encontra os melhores momentos, reconstrói a narrativa e entrega vídeos verticais com enquadramento, ritmo e legendas.</p>

          <div className="upload-composer" id="workflow">
            <div className="composer-topline">
              <div><span className="composer-kicker">Comece seu primeiro projeto</span><strong>Importe um vídeo longo</strong></div>
              <span className="private-pill"><Check size={12} /> Processamento privado</span>
            </div>
            <div className="source-row">
              <a className="link-field" href="/signup"><Link2 size={18} /><span>Cole um link público do YouTube</span></a>
              <span className="source-divider">ou</span>
              <Link className="upload-button" href="/studio?source=upload"><Upload size={17} /> Enviar arquivo</Link>
            </div>
            <div className="composer-footer">
              <span>MP4, MOV, MKV e WebM</span><span className="footer-dot" /><span>Até 4K</span>
              <a href="/signup">Começar agora <ArrowRight size={13} /></a>
            </div>
          </div>

          <div className="intelligence-row" id="recursos">
            {intelligence.map(({ icon: Icon, label }) => <div className="intelligence-item" key={label}><Icon size={16} /><span>{label}</span></div>)}
          </div>
        </div>

        <div className="product-visual" id="motor" aria-label="Prévia do editor NixClip">
          <div className="visual-chrome">
            <div className="chrome-dots"><span /><span /><span /></div>
            <span className="chrome-title">Projeto / Conversa sobre criatividade</span>
            <span className="chrome-status"><span /> Análise concluída</span>
          </div>
          <div className="visual-body">
            <aside className="mini-sidebar" aria-hidden="true">
              <span className="mini-brand">N</span><span className="mini-icon active"><WandSparkles size={16} /></span>
              <span className="mini-icon"><Captions size={16} /></span><span className="mini-icon"><ScanFace size={16} /></span><span className="mini-icon"><Frame size={16} /></span>
            </aside>
            <div className="preview-stage">
              <div className="preview-heading">
                <div><span>CLIP 01</span><strong>A ideia que muda todo o processo</strong></div>
                <div className="score-ring"><strong>94</strong><span>score</span></div>
              </div>
              <div className="vertical-video">
                <div className="video-light" /><div className="speaker speaker-left"><span /></div><div className="speaker speaker-right"><span /></div>
                <div className="tracking-frame"><span>TRACK 01</span></div>
                <div className="caption-preview"><span>VOCÊ NÃO PRECISA</span><strong>CRIAR MAIS</strong><span>PRECISA ESCOLHER MELHOR.</span></div>
                <button className="play-control" aria-label="Reproduzir prévia"><Play size={18} fill="currentColor" /></button>
              </div>
              <div className="timeline">
                <div className="timeline-ruler"><span>00:00</span><span>00:18</span><span>00:36</span></div>
                <div className="timeline-track"><div className="timeline-segment segment-a" /><div className="timeline-segment segment-b" /><div className="timeline-playhead" /></div>
                <div className="transcript-line"><span>Você não precisa criar mais.</span><strong>Precisa escolher melhor.</strong></div>
              </div>
            </div>
            <aside className="insight-panel">
              <span className="panel-label">POR QUE ESTE CORTE?</span><h2>Hook direto, ideia completa e conclusão forte.</h2>
              <div className="metric"><span>Hook</span><i><b style={{ width: '96%' }} /></i><strong>96</strong></div>
              <div className="metric"><span>Coerência</span><i><b style={{ width: '93%' }} /></i><strong>93</strong></div>
              <div className="metric"><span>Valor</span><i><b style={{ width: '91%' }} /></i><strong>91</strong></div>
              <div className="insight-note"><Sparkles size={15} /><p>A fala sustenta o contexto sem depender do vídeo original.</p></div>
            </aside>
          </div>
        </div>
      </section>
      <section className="proof-strip" aria-label="Fluxo NixClip"><span>IMPORT</span><i /><span>ANALYZE</span><i /><span>CURATE</span><i /><span>REFINE</span><i /><span>RENDER</span></section>
    </main>
  );
}
