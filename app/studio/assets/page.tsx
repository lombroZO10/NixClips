'use client';
/* eslint-disable @next/next/no-img-element, @next/next/no-html-link-for-pages */

import Link from 'next/link';
import { ChangeEvent, useEffect, useRef, useState } from 'react';
import { Clapperboard, FolderOpen, ImagePlus, LayoutDashboard, Play, Upload } from 'lucide-react';
import '../studio.css';

type Asset = { id: string; name: string; preview_url: string | null; content_type: string; size_bytes: number };
export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]); const [error, setError] = useState(''); const [uploading, setUploading] = useState(false); const input = useRef<HTMLInputElement>(null);
  async function refresh() { const response = await fetch('/api/assets'); if (response.ok) setAssets(await response.json()); }
  useEffect(() => {
    let active = true;
    fetch('/api/assets').then(async (response) => response.ok ? response.json() : []).then((data) => { if (active) setAssets(data); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  async function upload(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setError(''); setUploading(true); const form = new FormData(); form.append('file', file); const response = await fetch('/api/assets', { method: 'POST', body: form }); if (!response.ok) { const body = await response.json().catch(() => ({})); setError(body.detail ?? 'Não foi possível enviar este logo.'); } else await refresh(); setUploading(false); event.target.value = ''; }
  const navigate = (path: string) => (event: React.MouseEvent<HTMLAnchorElement>) => { event.preventDefault(); window.location.assign(path); };
  return <main className="studio-shell"><aside className="studio-sidebar template-sidebar"><a className="studio-brand" href="/"><span><Play size={12} fill="currentColor" /></span><strong>NixClip</strong></a><nav><a href="/studio" onClick={navigate('/studio')}><LayoutDashboard size={18} /><span>Novo projeto</span></a><a href="/studio/projects" onClick={navigate('/studio/projects')}><FolderOpen size={18} /><span>Projetos</span></a><a href="/studio/templates" onClick={navigate('/studio/templates')}><Clapperboard size={18} /><span>Templates</span></a><a className="active" href="/studio/assets" onClick={navigate('/studio/assets')}><ImagePlus size={18} /><span>Ativos</span></a></nav></aside><section className="studio-workspace project-detail"><header className="studio-header"><Link className="back-link" href="/studio/templates">Modelo de marca</Link><div className="engine-status"><i /><span>Biblioteca privada</span></div></header><div className="studio-content assets-page"><div className="project-detail-heading"><div><span className="step-label">BIBLIOTECA</span><h1>Seus ativos</h1><p>Logos privados, prontos para aplicar nos seus modelos.</p></div><button className="generate-button" onClick={() => input.current?.click()} disabled={uploading}><Upload size={16} /> {uploading ? 'Enviando…' : 'Enviar logo'}</button><input ref={input} hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={upload} /></div>{error && <div className="studio-error">{error}</div>}{assets.length ? <div className="asset-grid">{assets.map((asset) => <article className="asset-card" key={asset.id}>{asset.preview_url ? <img src={asset.preview_url} alt={asset.name} /> : <ImagePlus size={24} />}<div><strong>{asset.name}</strong><small>{Math.ceil(asset.size_bytes / 1024)} KB · logo</small></div></article>)}</div> : <div className="asset-empty"><ImagePlus size={26} /><h2>Adicione seu primeiro logo</h2><p>PNG, JPG ou WebP de até 5 MB. Seus arquivos ficam privados na sua conta.</p><button className="generate-button" onClick={() => input.current?.click()}><Upload size={16} /> Enviar logo</button></div>}</div></section></main>;
}
