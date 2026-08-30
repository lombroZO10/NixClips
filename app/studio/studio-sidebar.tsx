'use client';

import Link from 'next/link';
import { Clapperboard, FolderOpen, ImagePlus, LayoutDashboard, Play } from 'lucide-react';

type StudioSection = 'new' | 'projects' | 'templates' | 'assets';
const sections = [
  { id: 'new', label: 'Novo projeto', href: '/studio', icon: LayoutDashboard },
  { id: 'projects', label: 'Projetos', href: '/studio/projects', icon: FolderOpen },
  { id: 'templates', label: 'Templates', href: '/studio/templates', icon: Clapperboard },
  { id: 'assets', label: 'Ativos', href: '/studio/assets', icon: ImagePlus },
] as const;

export function StudioSidebar({ active, accountEmail, onSignOut }: { active: StudioSection; accountEmail?: string; onSignOut?: () => void }) {
  return <aside className="studio-sidebar"><Link className="studio-brand" href="/"><span><Play size={12} fill="currentColor" /></span><strong>NixClip</strong></Link><nav>{sections.map((section) => { const Icon = section.icon; return <a key={section.id} className={active === section.id ? 'active' : ''} href={section.href} onClick={(event) => { event.preventDefault(); window.location.assign(section.href); }}><Icon size={18} /><span>{section.label}</span></a>; })}</nav>{onSignOut && <div className="sidebar-bottom"><button className="user-card" onClick={onSignOut} title="Sair da conta"><span>{accountEmail?.slice(0, 2).toUpperCase() || 'NC'}</span><div><strong>{accountEmail || 'Workspace pessoal'}</strong><small>Sair da conta</small></div></button></div>}</aside>;
}
