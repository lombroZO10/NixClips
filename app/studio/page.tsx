'use client';

import Link from 'next/link';
import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft, ArrowRight, Captions, Check, ChevronDown, CircleGauge, Clapperboard, Download,
  FileVideo2, FolderOpen, Frame, History, LayoutDashboard, Link2, LoaderCircle,
  Menu, Play, ScanFace, Settings2, Sparkles, Upload, WandSparkles, X,
} from 'lucide-react';
import type { ProjectJob, ProjectPreferences } from '../../lib/contracts';
import { createFileProject, createUrlProject, getProject, processorHealth } from '../../lib/processor-client';
import './studio.css';

const defaultPreferences: ProjectPreferences = {
  language: 'auto', clipLength: 'medium', aspectRatio: '9:16', clipCount: 10,
  prompt: '', captions: true, autoReframe: true,
};

function bytes(size: number) {
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}

export default function StudioPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [sourceType, setSourceType] = useState<'file' | 'url'>('file');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [dragging, setDragging] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [job, setJob] = useState<ProjectJob | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    processorHealth(controller.signal).then(setOnline);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!job || job.stage === 'complete' || job.stage === 'failed') return;
    const timer = window.setInterval(async () => {
      try { setJob(await getProject(job.id)); } catch { /* keep last known state */ }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [job]);

  function selectFile(nextFile?: File) {
    if (!nextFile) return;
    const valid = nextFile.type.startsWith('video/') || /\.(mp4|mov|mkv|webm|m4v)$/i.test(nextFile.name);
    if (!valid) { setError('Escolha um arquivo de vídeo MP4, MOV, MKV ou WebM.'); return; }
    setError(''); setFile(nextFile);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]);
  }

  async function submit() {
    setError('');
    if (!online) { setError('O motor local está offline. Inicie o serviço do conversor para processar o vídeo.'); return; }
    if (sourceType === 'file' && !file) { setError('Selecione um vídeo para continuar.'); return; }
    if (sourceType === 'url' && !/^https?:\/\//i.test(url)) { setError('Informe um link público válido.'); return; }
    try {
      const next = sourceType === 'file'
        ? await createFileProject(file!, preferences)
        : await createUrlProject(url, preferences);
      setJob(next);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Não foi possível criar o projeto.'); }
  }

  const busy = job && job.stage !== 'complete' && job.stage !== 'failed';

  return (
    <main className="studio-shell">
      <aside className="studio-sidebar">
        <Link className="studio-brand" href="/"><span><Play size={12} fill="currentColor" /></span><strong>NixClip</strong></Link>
        <nav>
          <a className="active" href="#"><LayoutDashboard size={18} /><span>Novo projeto</span></a>
          <a href="#recentes"><History size={18} /><span>Projetos</span></a>
          <a href="#templates"><Clapperboard size={18} /><span>Templates</span></a>
        </nav>
        <div className="sidebar-bottom">
          <a href="#settings"><Settings2 size={18} /><span>Configurações</span></a>
          <div className="user-card"><span>NT</span><div><strong>Workspace pessoal</strong><small>Plano local</small></div></div>
        </div>
      </aside>

      <section className="studio-workspace">
        <header className="studio-header">
          <button className="mobile-menu" aria-label="Abrir menu"><Menu size={20} /></button>
          <div><span>STUDIO</span><h1>Novo projeto</h1></div>
          <div className={`engine-status ${online ? 'online' : online === false ? 'offline' : ''}`}>
            <i /> <span>{online === null ? 'Verificando motor' : online ? 'Motor local conectado' : 'Motor local offline'}</span>
          </div>
        </header>

        <div className="studio-content">
          <div className="project-intro">
            <div><span className="step-label">01 — FONTE</span><h2>Qual vídeo vamos transformar?</h2><p>Importe o conteúdo original. A análise preserva o contexto antes de selecionar os cortes.</p></div>
            <span className="privacy-badge"><Check size={13} /> Seus arquivos permanecem privados</span>
          </div>

          <div className="source-tabs">
            <button className={sourceType === 'file' ? 'active' : ''} onClick={() => setSourceType('file')}><Upload size={16} /> Arquivo local</button>
            <button className={sourceType === 'url' ? 'active' : ''} onClick={() => setSourceType('url')}><Link2 size={16} /> Link público</button>
          </div>

          <div className="creation-grid">
            <section className="source-card">
              {sourceType === 'file' ? (
                file ? (
                  <div className="selected-file">
                    <div className="file-preview"><FileVideo2 size={32} /><span>VÍDEO</span></div>
                    <div className="file-copy"><span>ARQUIVO SELECIONADO</span><strong>{file.name}</strong><small>{bytes(file.size)} · pronto para importação</small></div>
                    <button onClick={() => setFile(null)} aria-label="Remover arquivo"><X size={17} /></button>
                  </div>
                ) : (
                  <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} onClick={() => inputRef.current?.click()}>
                    <input ref={inputRef} type="file" accept="video/*,.mkv" hidden onChange={(event: ChangeEvent<HTMLInputElement>) => selectFile(event.target.files?.[0])} />
                    <span className="upload-orbit"><Upload size={25} /></span>
                    <h3>Solte seu vídeo aqui</h3><p>ou clique para selecionar no computador</p>
                    <button type="button"><FolderOpen size={16} /> Escolher arquivo</button>
                    <small>MP4, MOV, MKV ou WebM · resolução de até 4K</small>
                  </div>
                )
              ) : (
                <div className="url-source">
                  <span className="upload-orbit"><Link2 size={25} /></span><h3>Importar por link</h3><p>YouTube ou URL pública direta para um vídeo.</p>
                  <label><Link2 size={17} /><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." /></label>
                </div>
              )}

              <div className="analysis-route">
                <div><span><Upload size={14} /></span><small>IMPORT</small></div><i />
                <div><span><WandSparkles size={14} /></span><small>ANALYZE</small></div><i />
                <div><span><CircleGauge size={14} /></span><small>CURATE</small></div><i />
                <div><span><Frame size={14} /></span><small>RENDER</small></div>
              </div>
            </section>

            <aside className="settings-card">
              <div className="settings-title"><div><span className="step-label">02 — DIREÇÃO</span><h3>Configuração dos cortes</h3></div><Settings2 size={19} /></div>
              <label className="setting-field"><span>Idioma falado</span><div className="select-shell"><select value={preferences.language} onChange={(event) => setPreferences({ ...preferences, language: event.target.value as ProjectPreferences['language'] })}><option value="auto">Detectar automaticamente</option><option value="pt">Português</option><option value="en">Inglês</option><option value="es">Espanhol</option></select><ChevronDown size={15} /></div></label>
              <div className="setting-field"><span>Duração preferida</span><div className="segmented">{(['short','medium','long'] as const).map((length) => <button key={length} className={preferences.clipLength === length ? 'active' : ''} onClick={() => setPreferences({ ...preferences, clipLength: length })}>{length === 'short' ? '15–30s' : length === 'medium' ? '30–60s' : '60–90s'}</button>)}</div></div>
              <div className="setting-field"><span>Quantidade de cortes</span><div className="segmented">{([5, 10, 15] as const).map((count) => <button key={count} className={preferences.clipCount === count ? 'active' : ''} onClick={() => setPreferences({ ...preferences, clipCount: count })}>{count}</button>)}</div></div>
              <div className="setting-field"><span>Formato de saída</span><div className="ratio-options">{(['9:16','1:1','16:9'] as const).map((ratio) => <button key={ratio} className={preferences.aspectRatio === ratio ? 'active' : ''} onClick={() => setPreferences({ ...preferences, aspectRatio: ratio })}><i className={`ratio ratio-${ratio.replace(':','')}`} />{ratio}</button>)}</div></div>
              <label className="setting-field"><span>Direção criativa <small>opcional</small></span><textarea value={preferences.prompt} onChange={(event) => setPreferences({ ...preferences, prompt: event.target.value })} placeholder="Ex.: encontre opiniões fortes e explicações que funcionem sem contexto..." /></label>
              <div className="toggle-row"><div><Captions size={17} /><span>Legendas dinâmicas</span></div><button className={preferences.captions ? 'on' : ''} onClick={() => setPreferences({ ...preferences, captions: !preferences.captions })}><i /></button></div>
              <div className="toggle-row"><div><ScanFace size={17} /><span>Foco automático em rostos</span></div><button className={preferences.autoReframe ? 'on' : ''} onClick={() => setPreferences({ ...preferences, autoReframe: !preferences.autoReframe })}><i /></button></div>
            </aside>
          </div>

          {error && <div className="studio-error" role="alert">{error}</div>}
          {job && <div className={`job-progress ${job.stage === 'failed' ? 'failed' : ''}`}><div><LoaderCircle className={busy ? 'spin' : ''} size={18} /><span><strong>{job.title}</strong><small>{job.message}</small></span></div><div className="progress-bar"><i style={{ width: `${job.progress}%` }} /></div><strong>{job.progress}%</strong></div>}

          {job?.stage === 'complete' && job.clips.length > 0 && (
            <section className="results-section">
              <div className="results-heading"><div><span className="step-label">03 — RESULTADOS</span><h2>Cortes prontos para revisar</h2></div><span>{job.clips.length} clipes gerados</span></div>
              <div className="results-grid">
                {job.clips.map((clip, index) => (
                  <article className="result-card" key={clip.id}>
                    <div className="result-video">
                      {clip.outputUrl ? <video src={clip.outputUrl} controls preload="metadata" /> : <div><Play size={20} /></div>}
                      <span className="clip-index">CLIP {String(index + 1).padStart(2, '0')}</span>
                      <span className="clip-score"><strong>{clip.qualityScore}</strong> score</span>
                    </div>
                    <div className="result-copy">
                      <strong>{clip.title}</strong>
                      <span>{Math.round((clip.endMs - clip.startMs) / 1000)} segundos{clip.reframeMode ? ` · ${clip.reframeMode === 'face-aware' ? 'foco em rostos' : clip.reframeMode === 'fit' ? 'quadro preservado' : 'foco central'}` : ''}</span>
                      {clip.reasons && clip.reasons.length > 0 && <div className="reason-list">{clip.reasons.map((reason) => <small key={reason}>{reason}</small>)}</div>}
                      {clip.scoreBreakdown && (
                        <details className="score-details">
                          <summary>Por que este corte?</summary>
                          <div><span>Gancho <b>{clip.scoreBreakdown.hook}</b></span><span>Coerência <b>{clip.scoreBreakdown.coherence}</b></span><span>Valor <b>{clip.scoreBreakdown.value}</b></span><span>Entrega <b>{clip.scoreBreakdown.delivery}</b></span></div>
                        </details>
                      )}
                    </div>
                    {clip.outputUrl && <a href={clip.outputUrl} download><Download size={14} /> Baixar MP4</a>}
                  </article>
                ))}
              </div>
            </section>
          )}

          <div className="studio-actions">
            <Link href="/"><ArrowLeft size={16} /> Voltar</Link>
            <button className="generate-button" disabled={Boolean(busy)} onClick={submit}><Sparkles size={17} /> {busy ? 'Processando vídeo' : 'Gerar cortes'} <ArrowRight size={17} /></button>
          </div>
        </div>
      </section>
    </main>
  );
}
