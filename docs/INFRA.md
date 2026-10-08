# Infraestrutura — llm-gateway

## Ambientes

| Ambiente | Onde | Para quê | Chama API paga? |
|---|---|---|---|
| **Local** | PC do Leandro, docker compose | Desenvolvimento, testes de caos, k6 | Só no benchmark, com confirmação |
| **CI** | GitHub Actions | Lint, tipos, testes, build da imagem | **Nunca** (OpenRouter simulado) |
| **Produção** | VPS compartilhada (8 GB RAM, sem GPU) | Servir o iRacingEng e outros apps | Sim, com orçamento por app |

Não há ambiente de homologação separado: o compose local reproduz a produção.

## Containers

| Serviço | Imagem | Porta interna | Exposto? | Desde | Memória (estimativa) |
|---|---|---|---|---|---|
| `gateway` | imagem própria (Python 3.12 slim) | 8000 | Sim, via proxy reverso | V1 | 150–300 MB |
| `postgres` | `pgvector/pgvector:pg17` | 5432 | Não | V1 | 300–500 MB |
| `grafana` | `grafana/grafana-oss` | 3000 | Só por túnel SSH ou proxy com login | V1 | 100–200 MB |
| `redis` | `redis:7-alpine` (`maxmemory` 128 MB, LRU) | 6379 | Não | V2 | ≤ 150 MB |
| `prometheus` | `prom/prometheus` (retenção 15 dias) | 9090 | Não | V3 | 200–300 MB |
| `otel-collector` + armazenamento de traços | `otel/opentelemetry-collector-contrib` + Grafana Tempo (a confirmar na S7) | 4317 | Não | V3 | 200–400 MB |

**Total estimado:** ~1,1–1,9 GB. Valores a confirmar com `docker stats` na S4 e na S7. Cada serviço recebe
`mem_limit` no compose para não afetar os outros projetos da VPS.

Rede: uma rede docker própria (`llm-gateway`). Apenas o `gateway` publica porta, e só em `127.0.0.1`.

## Produção na VPS

- **Porta própria** do gateway em `127.0.0.1` (ex.: `8710`, a confirmar contra as portas em uso).
- **Proxy reverso:** novo bloco no nginx existente para um subdomínio (ex.: `gateway.<seu-dominio>`), com TLS.
  Antes de mexer: backup da configuração atual, `nginx -t` e ok do Leandro.
- **Deploy:** manual e com ok. `docker compose pull && docker compose up -d` de uma tag publicada.
  Sem deploy automático enquanto a VPS for compartilhada.
- **Rollback:** voltar para a tag anterior no compose; migrações do Alembic sempre com `downgrade`.
- **Saúde:** `GET /health` (gateway, Postgres, Redis) e healthcheck do docker.

## CI/CD (GitHub Actions)

| Workflow | Gatilho | Etapas |
|---|---|---|
| `ci.yml` | push e PR | `uv sync` → `ruff check` → `ruff format --check` → `mypy` → `pytest` (Postgres e Redis como services) |
| `release.yml` | tag `v*` | Build da imagem → publica no GitHub Container Registry (`ghcr.io`) |

- Testes nunca usam chave real. `pytest -m live` só roda localmente e de forma manual.
- O único segredo no GitHub é o `GITHUB_TOKEN` padrão, usado para publicar a imagem.

## Segredos

| Segredo | Onde fica | Fase |
|---|---|---|
| `OPENROUTER_API_KEY` | `.env` local e `.env` na VPS | V0 |
| Chaves dos apps | `.env` como hash SHA-256 | V1 |
| `DATABASE_URL`, `REDIS_URL` | `.env` | V1/V2 |
| `GRAFANA_ADMIN_PASSWORD` | `.env` | V1 |
| `TYPESAFE_API_KEY` | `.env` | V0 (teste simulado) |

Regras: `.env` no `.gitignore`; `.env.example` com chaves vazias; nenhum segredo em log, commit, issue ou conversa.

## Dados, backup e retenção

| Dado | Retenção | Backup |
|---|---|---|
| Registro de chamadas (metadados) | Indefinida | `pg_dump` diário; 7 diários + 4 semanais |
| Texto das perguntas | Desligado por padrão; se ligado, apagado no prazo configurado | Junto com o banco |
| Cache e contadores (Redis) | Expira sozinho | Não precisa: o Postgres é a fonte da verdade |
| Gabarito e respostas brutas do benchmark | Fora do git, só local | Responsabilidade do Leandro |

O backup é restaurado num container local uma vez antes do primeiro deploy, para provar que funciona.

## Custos de operação

| Item | Custo |
|---|---|
| VPS | Já existente |
| OpenRouter | Por uso; teto pelo orçamento por app; taxa de ~5,5% sobre créditos |
| Benchmark V0 | US$ 4–7 (estimativa) |
| Jev | ~US$ 0,04 por milhão de tokens de entrada (centavos no teste da V0) |
| GitHub Actions e GHCR | Gratuito para repositório público |
