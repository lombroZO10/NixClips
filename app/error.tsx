'use client';

export default function GlobalError() {
  return <html lang="pt-BR"><body style={{ margin: 0, minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#06060b', color: '#eeeaf2', fontFamily: 'Arial, sans-serif' }}><main style={{ maxWidth: 420, padding: 32, textAlign: 'center' }}><p style={{ color: '#c98cff', fontSize: 12, letterSpacing: '.12em' }}>NIXCLIP</p><h1 style={{ margin: '8px 0 12px', fontSize: 28 }}>Atualização concluída</h1><p style={{ color: '#a8a1ad', lineHeight: 1.55 }}>Esta tela ficou aberta durante uma atualização. Recarregue para continuar no Studio.</p><button onClick={() => window.location.reload()} style={{ marginTop: 16, padding: '12px 18px', border: 0, borderRadius: 9, color: '#fff', background: 'linear-gradient(100deg,#8c2bfa,#d719a8,#ff234b)', cursor: 'pointer' }}>Recarregar Studio</button></main></body></html>;
}
