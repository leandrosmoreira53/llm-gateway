# Arquitetura — llm-gateway

## Contexto

```
┌──────────────┐   HTTPS, formato OpenAI    ┌──────────────┐   HTTPS   ┌────────────┐
│ iRacingEng   │ ─────────────────────────► │ llm-gateway  │ ────────► │ OpenRouter │ ──► modelos
│ outros apps  │ ◄───────────────────────── │              │ ◄──────── │            │
└──────────────┘  resposta + x-gateway-*    └──────┬───────┘           └────────────┘
       │                                          │
       │ (gateway fora do ar)                     ├── PostgreSQL + pgvector (registro, feedback, embeddings)
       └──────────► OpenRouter direto             ├── Redis (cache exato, rate limit, contadores)
                                                  └── Prometheus / OpenTelemetry → Grafana
```

## Fluxo de uma requisição

| # | Etapa | Módulo | Se falhar |
|---|---|---|---|
| 1 | Autenticação da chave do app | `api/auth` | 401 no formato OpenAI |
| 2 | Rate limit e orçamento do app | `budget/` | 429 com `Retry-After`; acima do orçamento, só degraus baratos |
| 3 | Filtro de capacidade (contexto, visão, ferramentas, JSON) | `routing/capabilities.py` | 400 se nenhum modelo atende |
| 4 | Política de rota (regra, Jev ou aprendida) | `routing/policy.py` | Jev sem resposta no tempo-limite → regra |
| 5 | Cache exato | `cache/exact.py` | Redis fora → segue sem cache |
| 6 | Chamada ao OpenRouter com reservas e preferência de provedor | `providers/openrouter.py` | Próximo modelo da lista; circuit breaker |
| 7 | Checagem da resposta (citação, formato, recusa) | `validators/` | Sobe um degrau na escada (`routing/ladder.py`) |
| 8 | Registro da chamada | `store/` | Postgres fora → fila em memória limitada; descarte contado em métrica |

## Interfaces principais

```python
class Provider(Protocol):
    async def chat(self, request: ChatRequest, route: ResolvedRoute) -> ChatResult: ...
    async def stream(self, request: ChatRequest, route: ResolvedRoute) -> AsyncIterator[ChatChunk]: ...

class Policy(Protocol):
    async def choose(self, request: ChatRequest, candidates: list[ModelSpec]) -> RouteDecision: ...
    # RouteDecision: modelo escolhido, degrau inicial, descartados com motivo

class Validator(Protocol):
    def check(self, request: ChatRequest, result: ChatResult) -> ValidationResult: ...
```

Novos provedores (V4), políticas (Jev, aprendida) e checagens entram implementando essas interfaces, sem
alterar o fluxo.

## Configuração

| Arquivo | Conteúdo |
|---|---|
| `config/models.yaml` | Modelos: preço por milhão de tokens, contexto, visão, ferramentas, JSON |
| `config/routes.yaml` | Apelidos (`auto-engenheiro`, `auto-barato`, `auto`): piso de qualidade, escada, reservas, preferência de provedor, checagens |
| `config/budgets.yaml` | Por app: orçamento diário e mensal, rate limit |
| `.env` | Segredos e endereços (ver `.env.example`) |

## Modelo de dados (proposta)

**`requests`** (uma linha por chamada)

| Campo | Tipo | Observação |
|---|---|---|
| `id` | uuid | Também devolvido em `x-gateway-request-id` |
| `created_at` | timestamptz | |
| `app_id` | text | |
| `route_alias` | text | ex.: `auto-engenheiro` |
| `policy` | text | `rule`, `jev`, `learned`, `shadow` |
| `model_chosen` / `model_used` | text | Diferem quando a reserva respondeu |
| `provider` | text | Provedor que atendeu no OpenRouter |
| `ladder_step` | int | Degrau final da escada |
| `tokens_in` / `tokens_out` | int | |
| `cost_usd` | numeric | Lido de `usage.cost`; inclui as tentativas que falharam |
| `latency_ms` / `ttft_ms` | int | Total e até o primeiro token |
| `cache_hit` | bool | |
| `validations` | jsonb | Resultado de cada checagem por tentativa |
| `route_reason` | jsonb | Escolhido, descartados e motivo |
| `status` / `error_type` | text | |
| `prompt_hash` | text | Sempre |
| `prompt_text` / `expires_at` | text / timestamptz | Só com opção ligada; apagado no prazo |

**`feedback`** (V3): `request_id`, `app_id`, `rating` (`up`/`down`), `comment`, `created_at`.

**`task_embeddings`** (V3): `request_id`, `task_type`, `embedding vector(n)`.

## Modos de falha

| Falha | Comportamento esperado | Teste |
|---|---|---|
| OpenRouter com 5xx ou lento | Reserva; circuit breaker abre para o modelo | respx + caos |
| Todos os modelos falham | 502 no formato OpenAI, chamada registrada | respx |
| Redis fora | Sem cache; rate limit em memória | caos |
| Postgres fora | Gateway responde; registro em fila limitada | caos |
| Jev fora ou lento | Política de regra | respx |
| Gateway fora | O cliente (iRacingEng) chama o OpenRouter direto | iRacingEng |

As decisões que justificam esse desenho estão em [adr/](adr/).
