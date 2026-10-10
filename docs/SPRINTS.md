# Sprints — llm-gateway

**Cadência:** 1 semana (segunda a domingo). **Total:** 10 sprints + Sprint 0, sendo 8 para o MVP (`v1.0.0`)
e 2 opcionais (V4).

**Ritos (time de uma pessoa + Claude):**
- **Planejamento** (segunda, 15 min): confirmar o escopo da sprint nesta página.
- **Revisão** (domingo): demo, atualização do `CHANGELOG.md`, da tabela de resultados e das datas do roadmap.

**Definição de pronto (vale para toda tarefa):**
- Código com testes; nenhum teste chama API paga (OpenRouter simulado com `respx`).
- `ruff` e `mypy` limpos; CI verde.
- Documentação afetada atualizada (README, ARCHITECTURE, INFRA ou ADR).
- Nenhum segredo no código, nos logs ou nos commits.
- Merge via PR revisado pelo Leandro.

IDs: `GW-<sprint>.<n>`.

---

## Sprint 0 — Planejamento (07–11/10)

| ID | Tarefa |
|---|---|
| GW-0.1 | Plano, roadmap, sprints, arquitetura, infra, benchmark e ADRs |
| GW-0.2 | Criar o repositório `llm-gateway` no GitHub e dar acesso (Leandro) |
| GW-0.3 | Licença: **MIT** (decidido em 07/10) |
| GW-0.4 | README em inglês como padrão (`README.md`); versão em português em `README.pt-BR.md` |

**Aceite:** documentação revisada e aprovada; repositório criado.

---

## Sprint 1 — Fundação e cliente OpenRouter (12–18/10) · V0

| ID | Tarefa |
|---|---|
| GW-1.1 | Esqueleto do projeto: `uv`, layout `src/`, ruff, mypy estrito, pre-commit, pytest |
| GW-1.2 | CI no GitHub Actions: lint, tipos, testes |
| GW-1.3 | `providers/base.py` (interface) e `providers/openrouter.py`: chamada, `usage.cost`, tokens, latência, erros tipados |
| GW-1.4 | Formato do conjunto de dados (JSONL), leitor a partir de pasta externa (`BENCH_DATASET_PATH`) e conjunto público de exemplo |
| GW-1.5 | Divisão ajuste/teste 29/29 com semente fixa; IDs da divisão gravados e congelados |
| GW-1.6 | `LICENSE`, `.env.example`, `.gitignore` |

**Aceite:** CI verde; cliente testado offline; divisão gerada e versionada (só os IDs).

---

## Sprint 2 — Benchmark V0 (19–25/10) · release `v0.1.0`

| ID | Tarefa |
|---|---|
| GW-2.0 | Contexto congelado (decisão 2a): busca do iRacingEng no banco de staging, modos híbrido e com reordenação, e bloco de números da sessão de Bristol — feito em 10/10 |
| GW-2.1 | `bench/run.py`: roda os 15 modelos, o `openrouter/auto` e o Jev Router com o contexto congelado; respostas brutas fora do git; retomável; estimativa de custo e teto (US$ 8) |
| GW-2.2 | `validators/citation.py` e `validators/refusal.py` |
| GW-2.3 | `bench/grade.py`: juiz binário com gabarito |
| GW-2.4 | Revisão humana: 10 respostas por modelo (Leandro), via CSV; taxa de concordância com o juiz |
| GW-2.5 | `bench/simulate.py`: escada simulada e oráculo sobre as respostas gravadas |
| GW-2.6 | Jev Router (`typesafe/jev-router`) medido como router de mercado, registrando o modelo escolhido por pergunta |
| GW-2.7 | Tabela de resultados com intervalo de confiança no README |

**Aceite:** tabela publicada para os 15 modelos, `openrouter/auto`, Jev Router, escada com regra e oráculo;
gasto real registrado (estimativa: ~US$ 4; teto US$ 8).

---

## Sprint 3 — Núcleo do gateway (26/10–01/11) · V1

| ID | Tarefa |
|---|---|
| GW-3.1 | FastAPI: `POST /v1/chat/completions` (sem streaming), `GET /v1/models`, `GET /health` |
| GW-3.2 | Erros no formato da OpenAI |
| GW-3.3 | Autenticação por chave de app (guardada como hash) |
| GW-3.4 | `config/models.yaml` (preço, capacidades) e `config/routes.yaml` (apelidos, piso, reservas, provedor) |
| GW-3.5 | Filtro de capacidade e regra "mais barato acima do piso" com os números da V0 |
| GW-3.6 | Fallback de provedor (lista `models`) e roteamento de provedor (objeto `provider`) |
| GW-3.7 | Cabeçalhos `x-gateway-request-id`, `-model`, `-cost-usd`, `-route-reason`; motivo com escolhido e descartados |

**Aceite:** testes cobrindo rota, capacidade, fallback, autenticação e erros.

---

## Sprint 4 — Persistência, streaming e painel (02–08/11) · release `v0.2.0`

| ID | Tarefa |
|---|---|
| GW-4.1 | Streaming SSE, com custo lido do último bloco de `usage` |
| GW-4.2 | Postgres + SQLAlchemy 2 + Alembic; tabela de chamadas; gravação sem bloquear a resposta |
| GW-4.3 | Logs JSON |
| GW-4.4 | `docker-compose.yml`: gateway, Postgres (pgvector), Grafana |
| GW-4.5 | Painel de custos no Grafana, versionado em `ops/grafana/` |
| GW-4.6 | k6 com upstream simulado; sobrecarga p50/p95 no README |
| GW-4.7 | Teste **local** com o iRacingEng trocando só o endereço base |

**Aceite (V1 pronta):** iRacingEng funciona localmente; rota igual à da V0; reserva responde com o principal
derrubado; painel mostra as chamadas.

---

## Sprint 5 — Escada, cache, rate limit e deploy (09–15/11) · V2

| ID | Tarefa |
|---|---|
| GW-5.1 | `routing/ladder.py`: barato → checagem → caro; degrau e falha registrados |
| GW-5.2 | Circuit breaker por modelo |
| GW-5.3 | Cache exato no Redis; gateway segue funcionando sem Redis |
| GW-5.4 | Rate limit por app (token bucket no Redis, volta para memória); 429 com `Retry-After` |
| GW-5.5 | Deploy na VPS (com ok): compose, proxy reverso, TLS, backup (ver INFRA.md) |
| GW-5.6 | Ligação do iRacingEng em produção (com ok), com volta para o OpenRouter direto se o gateway cair |

**Aceite:** escada e cache testados; gateway no ar na VPS; iRacingEng com volta automática testada.

---

## Sprint 6 — Orçamento, Jev, sombra e caos (16–22/11) · release `v0.3.0`

| ID | Tarefa |
|---|---|
| GW-6.1 | Orçamento por app (diário e mensal); acima do teto, só degraus baratos |
| GW-6.2 | Modo sombra: responde com o modelo fixo e grava o que teria escolhido |
| GW-6.3 | Política Jev ao vivo no gateway (delegando ao `typesafe/jev-router`), com tempo-limite, volta para a regra e custo registrado |
| GW-6.4 | Testes de caos (docker): Redis fora, Postgres fora, OpenRouter com 5xx e lentidão |
| GW-6.5 | Benchmark V2 ao vivo: escada com regra × política Jev × Sonnet sozinho; comparar com a V0; k6 de novo |

**Aceite (V2 pronta):** tabela atualizada; testes de caos passando.

---

## Sprint 7 — Observabilidade e feedback (23–29/11) · V3

| ID | Tarefa |
|---|---|
| GW-7.1 | Métricas Prometheus (`/metrics`) |
| GW-7.2 | Painel Grafana completo: economia vs modelo fixo, subidas de degrau, p50/p95 |
| GW-7.3 | OpenTelemetry com convenções GenAI; coletor e armazenamento de traços |
| GW-7.4 | `POST /v1/feedback` e tabela de feedback |
| GW-7.5 | Botões 👍/👎 do iRacingEng ligados ao endpoint (com ok) |

**Aceite:** painel completo; traço de ponta a ponta visível; feedback gravado.

---

## Sprint 8 — Router que aprende (30/11–06/12) · release `v1.0.0`

| ID | Tarefa |
|---|---|
| GW-8.1 | Classificador de tipo de tarefa por regra |
| GW-8.2 | Embeddings + pgvector; classificador por vizinhos mais próximos |
| GW-8.3 | `routing/predictor.py`: probabilidade de sucesso por (tarefa, modelo) com prior Beta, ativa com ≥ 30 resultados |
| GW-8.4 | Benchmark "aprendido × regra" no conjunto de teste |
| GW-8.5 | README final, diagrama de arquitetura e estudo de caso para o portfólio |

**Aceite (MVP):** tabela com a linha "router aprendido", com o resultado que der.

---

## Sprint 9 — Áudio (07–13/12) · V4 opcional

| ID | Tarefa |
|---|---|
| GW-9.1 | Teste de provedores de voz → texto e texto → voz |
| GW-9.2 | `POST /v1/audio/transcriptions` e `POST /v1/audio/speech` atrás da interface de provedor |

## Sprint 10 — Experimentos (14–20/12) · release `v1.1.0` · V4 opcional

| ID | Tarefa |
|---|---|
| GW-10.1 | Cache semântico com pgvector, como experimento medido |
| GW-10.2 | Provedor direto (Anthropic/OpenAI) se o gasto justificar a taxa do OpenRouter |
| GW-10.3 | Segundo conjunto de benchmark com perguntas reais (com consentimento, sem dado pessoal) |
