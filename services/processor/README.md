# NixClip Processor

Serviço local responsável por importação, transcrição, curadoria e renderização. O frontend nunca decide timestamps nem monta comandos FFmpeg: ele envia preferências e acompanha um `ProjectJob`.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn nixclip_processor.main:app --app-dir src --host 127.0.0.1 --port 8788
```

O primeiro projeto baixa o modelo ASR configurado. O padrão `small` favorece qualidade em português; altere `NIXCLIP_ASR_MODEL` em `.env` quando houver GPU adequada.

## Motor editorial v2

- gera e compara diferentes inícios e finais em vez de aceitar a primeira janela possível;
- favorece pausas naturais, pensamentos completos e fala clara;
- remove cortes sobrepostos ou semanticamente repetidos;
- devolve score detalhado e motivos editoriais para cada resultado;
- reutiliza transcrições persistidas em novas tentativas;
- usa detecção facial amostrada para posicionar o recorte vertical, com fallback central seguro.
