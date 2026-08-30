import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '../../../../lib/supabase-server';

const PROCESSOR_URL = process.env.PROCESSOR_URL ?? process.env.NEXT_PUBLIC_PROCESSOR_URL ?? 'http://127.0.0.1:8788';

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await getSupabaseServerClient(); if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser(); if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const { id } = await params; const { data: project, error } = await supabase.from('projects').select('*').eq('id', id).eq('owner_id', user.id).single();
  if (error || !project?.processor_project_id) return NextResponse.json({ detail: 'Projeto não encontrado.' }, { status: 404 });
  const response = await fetch(`${PROCESSOR_URL}/api/v1/projects/${project.processor_project_id}`, { cache: 'no-store' });
  if (!response.ok) return NextResponse.json(await response.json().catch(() => ({ detail: 'Processador indisponível.' })), { status: response.status });
  const job = await response.json();
  await supabase.from('projects').update({ stage: job.stage, progress: job.progress, message: job.message, error: job.error ?? null, media: job.media ?? null }).eq('id', id).eq('owner_id', user.id);
  if (Array.isArray(job.clips) && job.stage === 'complete') for (const clip of job.clips) await supabase.from('clips').upsert({ project_id: id, title: clip.title, start_ms: clip.startMs, end_ms: clip.endMs, quality_score: clip.qualityScore, output_url: clip.outputUrl ?? null, score_breakdown: clip.scoreBreakdown ?? null, reasons: clip.reasons ?? null, transcript_excerpt: clip.transcriptExcerpt ?? null }, { onConflict: 'project_id,title,start_ms' });
  return NextResponse.json({ ...job, id });
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await getSupabaseServerClient();
  if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const { id } = await params;
  const { data: project } = await supabase.from('projects').select('id,processor_project_id').eq('id', id).eq('owner_id', user.id).single();
  if (!project) return NextResponse.json({ detail: 'Projeto não encontrado.' }, { status: 404 });
  const response = await fetch(`${PROCESSOR_URL}/api/v1/projects/${project.processor_project_id}`, { method: 'DELETE' }).catch(() => null);
  const { error } = await supabase.from('projects').delete().eq('id', id).eq('owner_id', user.id);
  if (error) return NextResponse.json({ detail: 'Não foi possível excluir o projeto.' }, { status: 500 });
  return NextResponse.json({ ok: true, processorRemoved: Boolean(response?.ok) });
}
