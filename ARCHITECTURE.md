# Arquitetura do NixClip

O NixClip é dividido em duas superfícies com responsabilidades rígidas.

## Web

- Vinext/React para landing page, Studio e editor.
- D1/SQLite para usuários, projetos, estado dos jobs e metadados dos cortes.
- R2 para fontes e resultados quando a instalação estiver hospedada.
- O frontend usa os contratos de `lib/contracts.ts`; ele não inventa timestamps nem executa FFmpeg.

## Processor

- FastAPI local-first em `services/processor`.
- SQLite próprio para a fila e recuperação dos jobs locais.
- FFprobe/FFmpeg empacotados no workspace para inspeção e renderização reproduzível.
- faster-whisper para VAD, transcrição e timestamps por palavra.
- yt-dlp apenas para links públicos autorizados pelo usuário.

## Pipeline

```text
PENDING → IMPORT → ANALYZE → CURATE → REFINE → RENDER → COMPLETE
```

1. `IMPORT`: recebe ou baixa a fonte e valida as faixas com FFprobe.
2. `ANALYZE`: transcreve e produz um documento temporal persistente.
3. `CURATE`: gera múltiplas janelas narrativas, avalia gancho, coerência, valor, emoção, clareza e relevância, e remove candidatos semelhantes.
4. `REFINE`: ajusta os limites usando pausas reais, pontuação e confiança das palavras.
5. `RENDER`: detecta o foco dominante em rostos, compõe o formato escolhido e produz legendas alinhadas sem alterar as decisões editoriais.

O ranking é explicável: cada `ClipResult` carrega dimensões, penalidades e os principais motivos da seleção. A transcrição temporal é reutilizada em novas tentativas para evitar repetir a etapa mais cara.

O contrato persistido é a fonte da verdade. Preview, editor, exportação e histórico devem sempre derivar do mesmo projeto para impedir divergência entre UI e vídeo final.

## Hospedagem

A interface, autenticação, banco e blobs podem operar em camada gratuita. O processamento de vídeo não deve ser colocado em função serverless curta: ASR e renderização exigem processo persistente, FFmpeg e, para boa velocidade, GPU. No modo pessoal o Processor roda na própria máquina; posteriormente ele pode ser movido sem alterar os contratos da web.
