import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '../../../lib/supabase-server';

const PROCESSOR_URL = process.env.PROCESSOR_URL ?? process.env.NEXT_PUBLIC_PROCESSOR_URL ?? 'http://127.0.0.1:8788';

async function applyTemplate(supabase: NonNullable<Awaited<ReturnType<typeof getSupabaseServerClient>>>, userId: string, preferences: Record<string, unknown>) {
  const templateId = preferences.brandTemplateId;
  if (typeof templateId !== 'string' || !templateId) return preferences;
  const { data: template } = await supabase.from('brand_templates').select('settings').eq('id', templateId).eq('owner_id', userId).single();
  if (!template) throw new Error('Modelo de marca não encontrado.');
  const settings = template.settings as Record<string, unknown>;
  return { ...preferences, aspectRatio: settings.aspectRatio ?? preferences.aspectRatio, autoReframe: settings.layout === 'fit' ? false : preferences.autoReframe, brandTemplate: settings };
}

export async function POST(request: Request) {
  const supabase = await getSupabaseServerClient();
  if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ detail: 'Faça login para criar um projeto.' }, { status: 401 });
  const contentType = request.headers.get('content-type') ?? '';
  let response: Response;
  let sourceUrl: string | null = null;
  let preferences: Record<string, unknown> = {};
  if (contentType.includes('multipart/form-data')) {
    const incoming = await request.formData();
    const form = new FormData(); const file = incoming.get('file');
    if (file instanceof File) form.append('file', file, file.name);
    preferences = await applyTemplate(supabase, user.id, JSON.parse(String(incoming.get('preferences') ?? '{}'))); form.append('preferences', JSON.stringify(preferences));
    response = await fetch(`${PROCESSOR_URL}/api/v1/projects/upload`, { method: 'POST', body: form });
  } else {
    const body = await request.json() as { url: string; preferences: Record<string, unknown> };
    sourceUrl = body.url; preferences = await applyTemplate(supabase, user.id, body.preferences ?? {});
    response = await fetch(`${PROCESSOR_URL}/api/v1/projects/url`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ...body, preferences }) });
  }
  if (!response.ok) return NextResponse.json(await response.json().catch(() => ({ detail: 'O processador recusou a solicitação.' })), { status: response.status });
  const job = await response.json() as { id: string; title: string; sourceName?: string; stage: string; progress: number; message: string; createdAt: string };
  const { data: saved, error } = await supabase.from('projects').insert({ owner_id: user.id, processor_project_id: job.id, title: job.title, source_name: job.sourceName ?? null, source_url: sourceUrl, stage: job.stage, progress: job.progress, message: job.message }).select('id').single();
  if (error) return NextResponse.json({ detail: 'Projeto criado, mas não foi possível registrar sua propriedade.' }, { status: 500 });
  return NextResponse.json({ ...job, id: saved.id, processorProjectId: job.id }, { status: 202 });
}

export async function GET() {
  const supabase = await getSupabaseServerClient();
  if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const { data, error } = await supabase.from('projects').select('id,title,source_name,stage,progress,message,error,created_at,updated_at,clips(count)').eq('owner_id', user.id).order('created_at', { ascending: false });
  if (error) return NextResponse.json({ detail: 'Não foi possível carregar seus projetos.' }, { status: 500 });
  return NextResponse.json((data ?? []).map((project: Record<string, unknown>) => ({ ...project, clipCount: Array.isArray(project.clips) ? (project.clips[0] as { count?: number })?.count ?? 0 : 0 })));
}
