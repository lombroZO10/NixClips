'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowLeft, Download, LoaderCircle, Play, Trash2 } from 'lucide-react';
import type { ProjectJob } from '../../../../lib/contracts';
import { getProject } from '../../../../lib/processor-client';
import '../../studio.css';
import { StudioSidebar } from '../../studio-sidebar';

export default function ProjectDetail({ params }: { params: Promise<{ id: string }> }) {
  const [job, setJob] = useState<ProjectJob | null>(null); const [id, setId] = useState(''); const [error, setError] = useState('');
  useEffect(() => { params.then(({ id: projectId }) => { setId(projectId); return getProject(projectId); }).then(setJob).catch(() => setError('Não foi possível carregar este projeto.')); }, [params]);
  useEffect(() => { if (!job || job.stage === 'complete' || job.stage === 'failed') return; const timer = window.setInterval(() => getProject(job.id).then(setJob).catch(() => undefined), 2000); return () => window.clearInterval(timer); }, [job]);
  async function remove() { if (!window.confirm('Excluir este projeto e seus cortes?')) return; const response = await fetch(`/api/projects/${id}`, { method: 'DELETE' }); if (response.ok) window.location.assign('/studio'); else setError('Não foi possível excluir o projeto.'); }
  return <main className="studio-shell"><StudioSidebar active="projects" /><section className="studio-workspace project-detail"><header className="studio-header"><Link className="back-link" href="/studio"><ArrowLeft size={16} /> Voltar para projetos</Link><div className="engine-status"><i /> <span>Workspace pessoal</span></div></header><div className="studio-content">{error ? <div className="studio-error">{error}</div> : !job ? <div className="project-loading"><LoaderCircle className="spin" size={22} /> Carregando projeto…</div> : <><div className="project-detail-heading"><div><span className="step-label">PROJETO</span><h1>{job.title}</h1><p>{job.sourceName ?? 'Vídeo importado'} · {job.stage === 'complete' ? 'Processamento concluído' : job.message}</p></div><button className="danger-button" onClick={remove}><Trash2 size={15} /> Excluir</button></div><div className="detail-progress"><div><span>{job.stage === 'complete' ? 'Cortes prontos' : 'Processando seu vídeo'}</span><strong>{job.progress}%</strong></div><div className="progress-bar"><i style={{ width: `${job.progress}%` }} /></div></div>{job.clips.length ? <div className="results-grid">{job.clips.map((clip, index) => <article className="result-card" key={clip.id}><div className="result-video">{clip.outputUrl ? <video src={clip.outputUrl} controls preload="metadata" /> : <div><Play size={20} /></div>}<span className="clip-index">CLIP {String(index + 1).padStart(2, '0')}</span><span className="clip-score"><strong>{clip.qualityScore}</strong> score</span></div><div className="result-copy"><strong>{clip.title}</strong><span>{Math.round((clip.endMs - clip.startMs) / 1000)} segundos</span></div>{clip.outputUrl && <a href={clip.outputUrl} download><Download size={14} /> Baixar MP4</a>}</article>)}</div> : <div className="project-empty-state"><span><Play size={20} /></span><h2>Os cortes aparecerão aqui</h2><p>Você poderá revisar e baixar cada versão assim que a análise terminar.</p></div>}</>}</div></section></main>;
}
