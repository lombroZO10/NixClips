'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, FolderOpen, Plus } from 'lucide-react';
import { listProjects, type ProjectSummary } from '../../../lib/processor-client';
import '../studio.css';
import { StudioSidebar } from '../studio-sidebar';

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  useEffect(() => { listProjects().then(setProjects).catch(() => undefined); }, []);
  return <main className="studio-shell"><StudioSidebar active="projects" /><section className="studio-workspace project-detail"><header className="studio-header"><Link className="back-link" href="/studio"><ArrowLeft size={16} /> Novo projeto</Link><div className="engine-status"><i /> <span>Workspace pessoal</span></div></header><div className="studio-content projects-page"><div className="project-detail-heading"><div><span className="step-label">BIBLIOTECA</span><h1>Seus projetos</h1><p>Todos os vídeos que você transformou no NixClip, em um só lugar.</p></div><Link className="generate-button" href="/studio"><Plus size={16} /> Novo projeto <ArrowRight size={16} /></Link></div>{projects.length === 0 ? <div className="project-empty-state"><span><FolderOpen size={20} /></span><h2>Nenhum projeto ainda</h2><p>Crie seu primeiro projeto para começar a montar sua biblioteca.</p><Link className="generate-button" href="/studio">Criar primeiro projeto <ArrowRight size={16} /></Link></div> : <div className="projects-list">{projects.map((project) => <Link className="project-row" href={`/studio/projects/${project.id}`} key={project.id}><span className={`project-state state-${project.stage}`} /><span className="project-row-copy"><strong>{project.title}</strong><small>{new Date(project.created_at).toLocaleDateString('pt-BR')} · {project.clipCount} cortes · {project.stage === 'complete' ? 'Concluído' : project.progress + '%'}</small></span><ArrowRight size={16} /></Link>)}</div>}</div></section></main>;
}
