# NixClip Processor

Serviço local responsável por importação, transcrição, curadoria e renderização. O frontend nunca decide timestamps nem monta comandos FFmpeg: ele envia preferências e acompanha um `ProjectJob`.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn nixclip_processor.main:app --app-dir src --host 127.0.0.1 --port 8788
```

O primeiro projeto baixa o modelo ASR configurado. O padrão `small` favorece qualidade em português; altere `NIXCLIP_ASR_MODEL` em `.env` quando houver GPU adequada.
