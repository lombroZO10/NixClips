import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '../../../lib/supabase-server';

const allowedTypes = new Set(['image/png', 'image/jpeg', 'image/webp']);
const extension = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' } as const;

export async function GET() {
  const supabase = await getSupabaseServerClient(); if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser(); if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const { data, error } = await supabase.from('brand_assets').select('id,name,kind,storage_path,content_type,size_bytes,created_at').eq('owner_id', user.id).order('created_at', { ascending: false });
  if (error) return NextResponse.json({ detail: 'Não foi possível carregar seus ativos.' }, { status: 500 });
  const assets = await Promise.all((data ?? []).map(async (asset) => {
    const { data: signed } = await supabase.storage.from('brand-assets').createSignedUrl(asset.storage_path, 3_600);
    return { ...asset, preview_url: signed?.signedUrl ?? null };
  }));
  return NextResponse.json(assets);
}

export async function POST(request: Request) {
  const supabase = await getSupabaseServerClient(); if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser(); if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const form = await request.formData(); const file = form.get('file');
  if (!(file instanceof File) || !allowedTypes.has(file.type) || file.size > 5 * 1024 * 1024) return NextResponse.json({ detail: 'Envie um logo PNG, JPG ou WebP de até 5 MB.' }, { status: 400 });
  const path = `${user.id}/${crypto.randomUUID()}.${extension[file.type as keyof typeof extension]}`;
  const { error: uploadError } = await supabase.storage.from('brand-assets').upload(path, file, { contentType: file.type, upsert: false });
  if (uploadError) return NextResponse.json({ detail: 'Não foi possível enviar o logo.' }, { status: 500 });
  const { data, error } = await supabase.from('brand_assets').insert({ owner_id: user.id, name: file.name, kind: 'logo', storage_path: path, content_type: file.type, size_bytes: file.size }).select('id,name,kind,content_type,size_bytes,created_at').single();
  if (error) { await supabase.storage.from('brand-assets').remove([path]); return NextResponse.json({ detail: 'Logo enviado, mas não foi possível registrá-lo.' }, { status: 500 }); }
  return NextResponse.json(data, { status: 201 });
}
