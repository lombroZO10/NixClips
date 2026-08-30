import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '../../../../lib/supabase-server';

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await getSupabaseServerClient();
  if (!supabase) return NextResponse.json({ detail: 'Autenticação indisponível.' }, { status: 503 });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ detail: 'Faça login.' }, { status: 401 });
  const { id } = await params;
  const { data: asset } = await supabase.from('brand_assets').select('id,storage_path').eq('id', id).eq('owner_id', user.id).single();
  if (!asset) return NextResponse.json({ detail: 'Ativo não encontrado.' }, { status: 404 });
  const { data: templates } = await supabase.from('brand_templates').select('id').eq('owner_id', user.id).filter('settings->>brandAssetId', 'eq', id).limit(1);
  if (templates?.length) return NextResponse.json({ detail: 'Este logo está em uso por um modelo. Remova-o do modelo antes de excluir.' }, { status: 409 });
  const { error: objectError } = await supabase.storage.from('brand-assets').remove([asset.storage_path]);
  if (objectError) return NextResponse.json({ detail: 'Não foi possível remover o arquivo do logo.' }, { status: 500 });
  const { error: recordError } = await supabase.from('brand_assets').delete().eq('id', id).eq('owner_id', user.id);
  if (recordError) return NextResponse.json({ detail: 'Arquivo removido, mas o cadastro não pôde ser atualizado.' }, { status: 500 });
  return NextResponse.json({ ok: true });
}
