# NixClip Processor

Worker headless de importação, transcrição, curadoria e renderização. O frontend envia a URL ou o arquivo e acompanha o `ProjectJob`; o worker controla timestamps, FFmpeg e o download.

## Download resiliente do YouTube

O importador usa uma fila serial por padrão e adiciona:

- `yt-dlp` nightly, `yt-dlp-ejs` e Deno;
- provider local `bgutil-ytdlp-pot-provider` conectado ao client `mweb`;
- cookies Netscape opcionais, montados como secret somente leitura;
- fallback configurável de `mweb` para `web_embedded`, `tv` e `android`;
- retries limitados, backoff exponencial com jitter e circuit breaker;
- cooldown global para HTTP 429, tráfego incomum e “not a bot”;
- intervalo entre downloads, pausa entre requests, limite de banda e concorrência;
- eventos JSON e diagnóstico em `GET /health`.

O comportamento dos clients não é equivalente. `mweb` com provider PO é o principal. `web_embedded` funciona apenas para vídeos incorporáveis. `tv` pode devolver somente formatos SABR/DRM dependendo da sessão, e `android` não aceita cookies de conta; por isso ele é usado sem o arquivo de cookies e apenas como último fallback para conteúdo público.

## Instalação recomendada — Ubuntu 22.04 + Docker

Instale Docker Engine e o plugin Compose pelo repositório oficial:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

Depois, dentro de `services/processor`, execute (use `sudo docker` se seu usuário não tiver acesso ao daemon):

```bash
cp config.example.env .env
mkdir -p data secrets
chmod 700 secrets
docker compose pull
docker compose build --pull
docker compose up -d
docker compose ps
docker compose logs -f nixclip-worker pot-provider
```

O Compose mantém o provider na rede Docker interna; a porta `4416` não é publicada na internet. O worker fica acessível somente em `127.0.0.1:8788` e deve ser publicado por um reverse proxy com TLS se o frontend for remoto.

### Preparar `cookies.txt`

Cookies só são necessários para conteúdo que realmente exige conta. Em uma máquina confiável com navegador:

1. abra uma janela privada, autentique-se no YouTube e não reutilize essa sessão em outra aba;
2. exporte apenas cookies de `youtube.com` no formato Mozilla/Netscape;
3. feche a janela privada sem voltar a abrir a sessão;
4. envie o arquivo para a VPS e restrinja a leitura:

```bash
scp youtube.cookies.txt usuario@SEU_IP:/tmp/youtube.cookies.txt
ssh usuario@SEU_IP
cd /caminho/NixClip/services/processor
install -m 600 /tmp/youtube.cookies.txt secrets/youtube.cookies.txt
rm /tmp/youtube.cookies.txt
docker compose restart nixclip-worker
```

A primeira linha deve ser `# Netscape HTTP Cookie File` ou `# HTTP Cookie File`, com finais de linha LF no Linux. O `/health` informa `file_missing`, `invalid_netscape_header` ou `expired_or_empty` sem expor o conteúdo.

Não existe refresh confiável de cookies Google totalmente headless: o worker detecta a expiração e interrompe com erro de autenticação até o secret ser substituído. Ele também não troca contas para continuar após rate limit/BotGuard; nessa situação, pausa globalmente e retoma após o cooldown configurado.

## Instalação Python direta

O modo Docker é preferível porque fixa Deno e o provider. Para executar apenas o worker no host:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip ffmpeg curl unzip
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
cd /caminho/NixClip/services/processor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -U --pre "yt-dlp[default]"
python -m pip install -U "bgutil-ytdlp-pot-provider>=1.3.2,<2"
python -m pip install -e ".[vision,diarization]"
```

Suba o provider em um container local e depois o worker:

```bash
docker run --name nixclip-pot-provider --restart unless-stopped -d --init \
  -p 127.0.0.1:4416:4416 \
  brainicism/bgutil-ytdlp-pot-provider:1.3.2

cp config.example.env .env
sed -i 's#http://pot-provider:4416#http://127.0.0.1:4416#' .env
NIXCLIP_YOUTUBE_COOKIE_FILE="$PWD/secrets/youtube.cookies.txt" \
  python -m uvicorn nixclip_processor.main:app --app-dir src --host 127.0.0.1 --port 8788
```

Verifique a instalação do plugin contra uma URL que você tem autorização para baixar:

```bash
yt-dlp -v --extractor-args "youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416" \
  --extractor-args "youtube:player_client=mweb" \
  --cookies secrets/youtube.cookies.txt \
  "URL_AUTORIZADA"
```

O log detalhado deve listar um provider `bgutil:http`. O plugin solicita tokens ligados ao vídeo/sessão quando necessário; o cache e a validade são responsabilidade do provider. O `yt-dlp` possui o framework nativo para consumir providers, mas não gera PO tokens sozinho, portanto não existe fallback embutido equivalente quando o provider está fora do ar.

## Configuração

Copie `config.example.env` para `.env`. Os controles principais são:

| Variável | Padrão | Finalidade |
|---|---:|---|
| `NIXCLIP_YOUTUBE_PLAYER_CLIENTS` | `mweb,web_embedded,tv,android` | ordem dos fallbacks |
| `NIXCLIP_YOUTUBE_DOWNLOAD_CONCURRENCY` | `1` | downloads simultâneos |
| `NIXCLIP_YOUTUBE_DOWNLOAD_DELAY` | `15` | segundos mínimos entre downloads |
| `NIXCLIP_YOUTUBE_SLEEP_REQUESTS` | `5` | pausa interna entre requests do extractor |
| `NIXCLIP_YOUTUBE_LIMIT_RATE` | `2000000` | teto aproximado em bytes/s |
| `NIXCLIP_YOUTUBE_MAX_ATTEMPTS` | `6` | tentativas totais por URL |
| `NIXCLIP_YOUTUBE_RATE_LIMIT_COOLDOWN` | `600` | pausa global após 429/BotGuard |

Para uma VPS já limitada, aumente o cooldown para `1800` ou mais e reduza a frequência da fila. Trocar client, cookie ou conta repetidamente não recupera um IP bloqueado e pode prolongar a limitação.

## Healthcheck e logs

```bash
curl -s http://127.0.0.1:8788/health | python3 -m json.tool
docker compose logs --since=30m nixclip-worker | grep '"event"'
```

O healthcheck expõe o último sucesso/falha, quantidade de falhas consecutivas, client usado, cooldown restante, estado sanitizado dos cookies e alcance TCP do provider. `status: degraded` mantém HTTP 200 para diferenciar diagnóstico de prontidão sem derrubar o container durante um cooldown deliberado.

Eventos permanentes — vídeo privado/removido, copyright, URL inválida ou bloqueio regional — não são repetidos. Falhas de rede e HTTP 403 recebem retries limitados. HTTP 429 e “not a bot” abrem o circuit breaker antes de uma nova tentativa.

## Testes

Os testes não acessam YouTube nem carregam credenciais:

```bash
cd /caminho/NixClip/services/processor
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

Não é tecnicamente possível garantir “50 vídeos no mesmo IP sem desafio”: essa decisão pertence ao YouTube e varia por IP, conta, conteúdo e padrão de tráfego. O teste de aceite operacional correto é rodar URLs autorizadas em baixa taxa, observar `/health` e confirmar que limitações produzem cooldown/retomada, não um loop agressivo nem quebra silenciosa da fila.
