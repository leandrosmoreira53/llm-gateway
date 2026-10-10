# Plano — llm-gateway (Router V3)

Versão 3, 2026-10-07 (Grafana e fallback de provedor adiantados para a V1; entram k6, rate limit, pgvector e
convenções GenAI do OpenTelemetry; `openrouter/auto` no benchmark; roteamento de provedor; endpoint de feedback;
volta do iRacingEng para o OpenRouter direto se o gateway cair). Versão 4, 2026-10-10: 15 modelos (com Qwen e
open source) e o Jev medido como router pelo OpenRouter (`typesafe/jev-router`). Versão 2: Jev passou para a V2 como política alternativa. Autor do pedido: Leandro. Projeto **separado** do iRacingEng, feito para portfólio
e para servir o iRacingEng e outros sistemas.

## 1. O que é

Um gateway de IA que recebe pedidos no formato da API da OpenAI, escolhe o modelo com melhor
**custo por resposta correta**, chama esse modelo pelo OpenRouter, confere a resposta e registra
tudo (custo, tempo, acerto). Com o tempo, ele usa esse histórico para escolher melhor.

```
iRacingEng (e outros apps)
        │  POST /v1/chat/completions  (formato OpenAI, model: "auto-engenheiro")
        ▼
┌──────────────────────────── llm-gateway ────────────────────────────┐
│ 1. Autenticação + orçamento do app                                   │
│ 2. Filtro de capacidade (contexto, visão, ferramentas, JSON)         │
│ 3. Política de rota (regras → histórico → probabilidade de sucesso)  │
│ 4. Cache exato (mesma pergunta idêntica = custo zero)                │
│ 5. Chamada ao OpenRouter (com lista de modelos reserva)              │
│ 6. Checagem da resposta (citação, formato, recusa)                   │
│      falhou → sobe um degrau na escada e tenta de novo               │
│ 7. Registro: modelo, tokens, custo, latência, checagem, degrau       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
                          OpenRouter
                               ▼
              Claude / GPT / Gemini / DeepSeek / ...
```

**Por que compatível com a OpenAI:** é o formato padrão do mercado (o próprio OpenRouter usa).
Qualquer cliente (biblioteca da OpenAI, LangChain, LlamaIndex, o iRacingEng) usa o gateway só
trocando o endereço. Não amarra a nenhum fornecedor.

## 2. O diferencial (o que vai no topo do README)

1. **Prova que economiza:** cada versão publica a tabela "router vs um modelo só" com acerto, custo por
   resposta correta e latência, medida num conjunto de teste real e separado.
2. **Escada com checagem:** modelo barato primeiro; checagem objetiva; só sobe para o caro se falhar.
3. **Benchmark de domínio real:** perguntas de engenharia de corrida (NASCAR no iRacing), não só perguntas
   genéricas. Gabarito escrito com IA e revisado pelo autor; revisão por engenheiro de setup pendente
   (decisão de 2026-10-08: publicar assim, informando o status).
4. **Números honestos:** o README mostra também o que não funcionou e os limites da medida.
5. **Decisão auditável:** toda rota grava por que aquele modelo foi escolhido e quais foram descartados.

## 3. O que veio do plano do analista (e o que mudou)

| Ideia do analista | No plano | Quando |
|---|---|---|
| Filtro de capacidade antes da decisão econômica | Sim, igual | V1 |
| "Mais barato que passa no piso de qualidade" como primeira regra | Sim, é a regra inicial | V1 |
| OpenRouter como estrada, não como cérebro | Sim. O gateway escolhe o **modelo**; o OpenRouter escolhe só o **provedor** que serve aquele modelo (objeto `provider`, ordenado por preço ou latência conforme a rota). O Auto Router do OpenRouter (`openrouter/auto`) não é usado para rotear: entra no benchmark como concorrente. | V0 / V1 |
| Histórico por chamada (tarefa, modelo, tokens, custo, latência, sucesso) | Sim, em Postgres | V1 |
| Custo esperado = custo ÷ probabilidade de sucesso | Sim, com a conta da escada (custo do barato + taxa de falha × custo do caro) | V2 |
| Fallback inteligente (falhou na checagem → outro modelo → registra) | Sim, é a escada | V2 |
| Fallback de provedor (modelo/provedor fora do ar → reserva) | Sim, lista `models` do OpenRouter; circuit breaker na V2 | V1 |
| Orçamento diário/premium | Sim, por app | V2 |
| Rate limit por app | Sim, token bucket no Redis; passou do limite → 429 no formato OpenAI | V2 |
| Cache exato (Redis) | Sim | V2 |
| Quality feedback com testes objetivos, não só "LLM deu nota 9" | Sim: checagem de citação + juiz binário com gabarito + amostra humana | V0 |
| Benchmark "custo por tarefa bem-sucedida" vs GPT-only / Claude-only / mais barato | Sim, é o produto principal | V0 e toda versão |
| Router que aprende com o histórico | Sim, quando houver ≥ 30 resultados avaliados por (tarefa, modelo) | V3 |
| Dashboard (custo, economia, % por modelo, sucesso) | Sim: Grafana simples lendo o Postgres na V1; completo com Prometheus na V3 | V1 / V3 |
| Second Brain do router (grafo de experiência) | Depois, se o histórico mostrar padrão que uma tabela não resolve | V4+ |
| LiteLLM na frente | **Não.** O gateway é o seu código; LiteLLM esconderia justamente a parte que vai no portfólio. Pode entrar como biblioteca de preços/tokens se ajudar. | — |
| Jev como cérebro | **Medido na V0 como router de mercado (`typesafe/jev-router`, pelo OpenRouter) e, na V2, como política alternativa plugável**, medida contra a regra no mesmo conjunto de teste. Se ganhar, vira a política principal; se perder, fica registrado no README. Não é a base porque é API fechada e paga (TypeSafe) e o gateway não pode parar se ela cair: sem resposta do Jev em X ms, vale a regra. Primeiro número já na V0. | V0 (router) / V2 (política) |
| Cache semântico | **Só como experimento medido**, com pgvector (sem banco vetorial separado). Em setup, "solto na entrada" e "solto na saída" são parecidos e têm resposta oposta. | V4 opcional |
| Ollama / modelos locais | Fora enquanto a VPS tiver 8 GB sem GPU. Pode rodar no seu PC em teste. | — |
| APIs diretas (Anthropic, OpenAI) além do OpenRouter | Só quando o gasto justificar a taxa do OpenRouter (~5,5%). A interface de provedor já nasce pronta para isso. | V4 |

Repositórios de referência (estudar, não copiar em bloco):
- **jman4162/llm-token-router** (Apache-2.0): escada com checagem, custo por sucesso verificado, sucesso por
  modelo com prior Beta. Principal referência.
- **lastlad/jev-model-router** (MIT): fórmula `utilidade = −custo − risco de qualidade`, modo sombra,
  eval com conjunto rotulado.
- **TokenTrim/jev-routing-experiment** (Apache-2.0): método de benchmark (separar ajuste e teste, congelar
  antes de medir, comparar com melhor modelo único e com o oráculo).
- **rahulrachh/llm-router** (sem licença: **só ler**): exemplos de teste de caos, circuit breaker e README honesto.

## 4. Fases

Cada fase termina com testes passando, CI verde e uma linha nova na tabela de resultados do README.

### V0 — Benchmark primeiro (sem gateway ainda)
Objetivo: saber, com dado, se rotear vale a pena antes de construir.
- Estrutura do repositório, CI, lint, testes.
- Cliente do OpenRouter (lendo `usage.cost`, tokens, tempo).
- Conjunto de teste: gabarito do iRacingEng (58 perguntas) dividido em **ajuste** e **teste** (29/29, sorteio
  com semente fixa). Ver §7 sobre privacidade.
- Avaliação: checagem de citação (automática), checagem de recusa (automática), juiz binário comparando com
  a resposta esperada, e amostra de 10 por modelo conferida por você.
- Rodar 15 modelos (decisão de 2026-10-10; slugs do OpenRouter conferidos no catálogo nesse dia):
  - **Fechados:** `anthropic/claude-sonnet-5.5`, `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`,
    `google/gemini-3.8-flash`.
  - **Open source (pesos publicados):** `qwen/qwen3.8-flash`, `qwen/qwen3.8-27b`, `qwen/qwen3.8-2.4t-a95b`,
    `deepseek/deepseek-v4.1-flash`, `deepseek/deepseek-v4-pro`, `moonshotai/kimi-k3`, `z-ai/glm-5.3`,
    `openai/gpt-oss-120b`, `meta-llama/llama-4-maverick`, `mistralai/mistral-small-2603`,
    `nvidia/nemotron-3-super-120b-a12b`.
  - Raciocínio no padrão de cada modelo; tokens de raciocínio registrados na tabela.
- Rodar também os **routers de mercado** como concorrentes, gravando qual modelo eles escolheram em cada pergunta
  (campo `model` da resposta): **`openrouter/auto`** (Auto Router do OpenRouter) e **`typesafe/jev-router`**
  (Jev Router da TypeSafe, no OpenRouter: escolhe modelo e nível de raciocínio).
- Simular a escada em cima das respostas gravadas (sem gastar de novo).
- **Pronto quando:** existe a tabela acerto × custo por resposta correta × latência para os 15 modelos, os dois
  routers de mercado (`openrouter/auto` e Jev Router), a escada com regra e o oráculo. Custo estimado pelos preços
  do catálogo: ~US$ 4 (modelos + juiz); **teto de US$ 8** (o script para sozinho se passar).

### V1 — Gateway funcional
- `POST /v1/chat/completions` e `GET /v1/models` no formato OpenAI (com e sem streaming).
- Apelidos de rota em YAML: `auto-engenheiro`, `auto-barato`, `auto` (genérico).
- Filtro de capacidade + regra "mais barato que passa no piso" usando os números da V0.
- Chave por app, segredo só em `.env`, `.env.example` vazio no repo.
- Tabela `chamadas` no Postgres (migrações com Alembic) com custo, tokens, latência, modelo, motivo da rota.
- Cabeçalhos de resposta: `x-gateway-request-id` (usado depois no feedback), `x-gateway-model`,
  `x-gateway-cost-usd`, `x-gateway-route-reason`.
- `GET /health` para os clientes saberem se o gateway está de pé (ver §7, volta do iRacingEng).
- **Roteamento de provedor:** cada rota em `routes.yaml` define o objeto `provider` do OpenRouter (ex.:
  `auto-barato` ordena por preço; `auto-engenheiro` por latência). O provedor que atendeu é gravado na tabela
  `chamadas`.
- **Fallback de provedor:** cada rota tem uma lista de modelos reserva, enviada no parâmetro `models` do
  OpenRouter. Se o principal cair, o OpenRouter tenta o próximo; o modelo que respondeu de fato é o que vai no
  registro e no cabeçalho `x-gateway-model`.
- **Painel de custos simples:** Grafana no docker compose, lendo direto a tabela `chamadas` do Postgres
  (custo por dia, custo por app, % por modelo, latência). Painel versionado em `ops/grafana/`.
- **Teste de carga com k6:** mede quanto o gateway adiciona de latência (p50/p95) em relação a chamar o
  OpenRouter direto, com o OpenRouter simulado para não gastar. O número vai para o README.
- **Pronto quando:** o iRacingEng (em teste local) troca só o endereço e funciona; a rota é igual à escolhida na V0;
  derrubar o modelo principal (simulado) faz a reserva responder; o painel mostra as chamadas.

### V2 — Escada, orçamento e cache
- Escada: barato → checagem → caro, com registro da falha e do degrau.
- **Política Jev ao vivo** (plugável, ao lado da regra): o gateway delega a escolha ao Jev Router (`typesafe/jev-router`, pelo OpenRouter, mesma chave). Tempo-limite com volta para a regra; custo registrado em cada chamada. Medida contra a regra no conjunto de teste (ver ADR 0004).
- Circuit breaker simples por modelo (a lista reserva já existe desde a V1).
- Orçamento por app (diário e mensal); passou do teto, só degraus baratos.
- **Rate limit por app** (token bucket no Redis): passou do limite, resposta 429 no formato OpenAI com
  `Retry-After`. Se o Redis cair, o limite passa a ser em memória (não trava o gateway).
- k6 de novo: latência com escada e cache ligados, e taxa de acerto do cache.
- Cache exato em Redis; o gateway continua funcionando se o Redis cair (teste de caos).
- **Modo sombra:** o gateway responde com o modelo fixo, mas registra o que teria escolhido.
- **Pronto quando:** benchmark mostra escada com regra vs política Jev vs Sonnet sozinho no conjunto de teste; teste de caos do Redis e do
  Postgres passando (o gateway não pode travar se o banco cair).

### V3 — Aprende com o histórico + painel
- Probabilidade de sucesso por (tipo de tarefa, modelo) com prior Beta, a partir das checagens e do 👍/👎 do usuário.
- **`POST /v1/feedback`**: o app envia `{request_id, nota: "up"|"down", comentario?}`, usando o
  `x-gateway-request-id` recebido na resposta. Autenticado pela chave do app; só aceita feedback de chamadas do
  próprio app. No iRacingEng, os botões 👍/👎 chamam esse endpoint.
- Classificador de tipo de tarefa (primeiro por regra; depois por vizinhos mais próximos com embeddings,
  guardados no próprio Postgres com **pgvector**).
- A regra só é trocada pelo modelo aprendido se ele ganhar no conjunto de teste.
- Métricas Prometheus + painel Grafana completo (custo do dia, economia vs modelo fixo, % por modelo, subidas de
  degrau, latência p50/p95), substituindo o painel simples da V1.
- OpenTelemetry nos traços, seguindo as **convenções semânticas GenAI** (modelo, tokens de entrada/saída,
  provedor como atributos padrão), para o traço abrir em qualquer ferramenta compatível.
- **Pronto quando:** a tabela mostra "aprendido vs regra" no teste, com o resultado que der (inclusive se perder).

### V4 — Áudio e além
- `POST /v1/audio/transcriptions` (voz → texto) e voz de resposta (texto → voz) para o chatbot que entende o
  piloto. O provedor de áudio é decidido com teste (o OpenRouter pode não cobrir; nesse caso entra um provedor
  direto atrás da mesma interface).
- APIs diretas quando o gasto justificar. Cache semântico (pgvector) só como experimento medido.
- Segundo conjunto de benchmark: perguntas reais do sistema (com consentimento e sem dado pessoal).

## 5. Stack

| Parte | Escolha | Por quê |
|---|---|---|
| Linguagem | Python 3.12 | Ecossistema de IA, rápido de iterar |
| API | FastAPI + Pydantic v2 + httpx (async) | Padrão de mercado, tipagem, OpenAPI automático |
| Banco | PostgreSQL + SQLAlchemy 2 + Alembic | Histórico e orçamento; migrações versionadas |
| Vetores | pgvector (a partir da V3) | Embeddings no mesmo Postgres, sem serviço extra |
| Cache/estado rápido | Redis (a partir da V2) | Cache exato, contadores de orçamento e rate limit |
| Observabilidade | Logs JSON + Grafana sobre Postgres (V1); Prometheus + OpenTelemetry GenAI (V3) | Mostra custo e saúde em tempo real |
| Testes | pytest, respx (simula o OpenRouter sem gastar), testes de caos com docker | Testa sem chave e sem custo |
| Carga | k6 (V1 e V2) | Prova quanto o gateway adiciona de latência |
| Qualidade | ruff, mypy, pre-commit | CI barra código fora do padrão |
| Entrega | Docker + docker compose; GitHub Actions (lint, testes, build da imagem) | Roda igual no PC e na VPS |
| Licença | MIT | Portfólio público |

## 6. Estrutura do repositório

```
llm-gateway/
├── src/gateway/
│   ├── api/            # rotas OpenAI-compatíveis, auth, erros no formato OpenAI
│   ├── routing/        # capabilities.py, policy.py (regras), ladder.py (escada), predictor.py (V3)
│   ├── providers/      # base.py (interface), openrouter.py; anthropic.py etc. só na V4
│   ├── validators/     # citation.py, refusal.py, schema.py
│   ├── budget/         # orçamento e rate limit por app
│   ├── cache/          # exact.py (V2)
│   ├── store/          # modelos do banco, gravação das chamadas
│   └── telemetry/      # logs, métricas, traços
├── bench/
│   ├── datasets/       # só o formato e um exemplo público; o gabarito real fica fora (ver §7)
│   ├── run.py          # roda modelos e grava respostas
│   ├── grade.py        # checagens + juiz
│   ├── simulate.py     # simula escada/router sobre respostas gravadas
│   ├── load/           # scripts k6 (teste de carga)
│   └── results/        # tabelas agregadas que vão para o README
├── config/             # models.yaml, routes.yaml (com modelos reserva), budgets.yaml
├── ops/grafana/        # painéis e datasources versionados
├── migrations/
├── tests/
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
└── README.md
```

## 7. Cuidados

- **Gabarito e manuais são privados.** O gabarito do iRacingEng traz trechos dos manuais do iRacing (direito
  autoral) e conhecimento da equipe. Se o repositório for público, o conjunto real fica **fora do git** (lido de
  uma pasta configurada) e só os resultados agregados são publicados. Um conjunto de exemplo público e pequeno
  vai no repo para quem quiser rodar.
- **Segredos:** chave do OpenRouter só em `.env`/ambiente. Nunca em log, commit ou conversa.
- **Dados de usuário:** o gateway grava custo e metadados; o texto das perguntas só com opção ligada e prazo de
  apagar.
- **iRacingEng não muda até você decidir.** Ligar o iRacingEng no gateway é trocar uma variável de ambiente
  (endereço base da API) depois do checkpoint de 02–08/11. Nada sobe na VPS antes disso sem o seu ok.
- **Gateway fora do ar não derruba o iRacingEng.** O gateway roda numa VPS só. Na ligação, o iRacingEng ganha
  tempo-limite curto para o gateway e, se ele não responder (ou `GET /health` falhar), volta a chamar o
  OpenRouter direto com o modelo fixo de hoje. A chamada fica marcada como "sem gateway" no log do iRacingEng.
  O README do gateway documenta esse padrão de cliente para outros apps.
- **VPS compartilhada:** quando subir, porta própria, sem mexer no nginx dos outros projetos sem backup e teste.

## 8. Como medir (a tabela do README)

Sempre no conjunto de **teste** (nunca no de ajuste), com configuração congelada antes de rodar:

| Alvo | Acerto | Custo por pergunta | Custo por resposta correta | Latência p50 / p95 |
|---|---|---|---|---|
| Sonnet 5.5 sozinho | | | | |
| Modelo mais barato sozinho | | | | |
| Melhor modelo único | | | | |
| OpenRouter Auto (`openrouter/auto`) | | | | |
| Jev Router (`typesafe/jev-router`) | | | | |
| Escada com regra (V0 simulada, V2 ao vivo) | | | | |
| Política Jev no gateway (V2) | | | | |
| Router aprendido (V3) | | | | |
| Oráculo (o mais barato que acertou, por pergunta) | | | | — |

Regra de decisão: vale a rota de menor custo por resposta correta **entre as que ficam no máximo 5 pontos
abaixo do melhor acerto**.

Já medido (iRacingEng, 2026-10-04, só custo): Sonnet 5.5 US$ 0,026 por pergunta, Opus 5.5 US$ 0,049,
Haiku 4.5 US$ 0,006. Acerto ainda não medido.

## 9. Primeiros passos

1. Você cria no GitHub um repositório vazio (sugestão: `llm-gateway`) e dá acesso ao Claude.
2. V0: estrutura + CI + benchmark dos 5 modelos (US$ 3–5).
3. Com a tabela da V0 na mão, decidimos a regra da V1.
