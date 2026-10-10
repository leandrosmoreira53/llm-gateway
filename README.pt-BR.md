# llm-gateway

[English](README.md) · **Português**

> Gateway de LLM compatível com a API da OpenAI que escolhe o modelo pelo **custo por resposta correta**
> e publica, com benchmark reproduzível, quanto economiza (e onde não economiza).
> Compara 13 modelos (fechados e open source, incluindo Qwen) e dois routers de mercado, **Jev Router** e
> OpenRouter Auto, no mesmo conjunto de teste congelado.

**Status:** `v0.1.0` — benchmark publicado (ver [Resultados](#resultados--v010-conjunto-de-teste)). Próximo: V1, o gateway.

---

## O problema

Aplicações com LLM costumam fixar um modelo caro para todas as chamadas. Boa parte das perguntas seria
respondida corretamente por um modelo várias vezes mais barato, mas trocar de modelo "no feeling" arrisca a
qualidade e ninguém mede o resultado.

## A solução

Um gateway que fica entre as aplicações e os modelos:

1. Recebe pedidos no formato da API da OpenAI. Qualquer cliente troca só o endereço base.
2. Descarta modelos que não atendem o pedido (contexto, visão, ferramentas, JSON).
3. Escolhe o modelo de menor **custo esperado por resposta correta**.
4. Chama o modelo via OpenRouter, com modelos reserva e escolha do provedor mais barato/rápido.
5. Confere a resposta com checagens objetivas. Se falhar, sobe um degrau na escada (modelo mais forte).
6. Registra tudo: modelo, provedor, tokens, custo, latência, checagens, degrau e **por que** a rota foi escolhida.

```
 Apps (iRacingEng, ...) ──► POST /v1/chat/completions  (model: "auto-engenheiro")
                                  │
            ┌──────────────── llm-gateway ────────────────┐
            │ auth + orçamento + rate limit               │
            │ filtro de capacidade                        │
            │ política de rota (regra │ Jev │ aprendida)  │
            │ cache exato                                 │
            │ escada com checagem ──► sobe se falhar      │
            │ registro auditável (Postgres)               │
            └──────────────────┬──────────────────────────┘
                               ▼
                          OpenRouter ──► Claude · GPT · Gemini · DeepSeek · ...
```

## Diferenciais

| | |
|---|---|
| **Prova que economiza** | Cada versão publica a tabela "router vs modelo único" com acerto, custo por resposta correta e latência, medida num conjunto de teste separado e congelado. |
| **Escada com checagem** | Modelo barato primeiro; sobe para o caro só quando uma checagem objetiva falha. |
| **Benchmark de domínio real** | 58 perguntas de engenharia de corrida (NASCAR Next Gen no iRacing), incluindo pegadinhas e perguntas sem resposta nas fontes. O gabarito foi escrito com IA e revisado pelo autor; a revisão por engenheiro de setup está pendente e será informada quando feita. |
| **Jev fora do hype, dentro do projeto** | O Jev Router da TypeSafe (`typesafe/jev-router`) escolhe modelo e nível de raciocínio por pedido. Ele é medido lado a lado, nas mesmas perguntas e com o mesmo contexto, com o custo completo. Na V2 pode entrar no gateway como política alternativa, com tempo-limite e volta para a regra; só vira a política principal se ganhar no conjunto de teste. |
| **Concorrente de mercado na tabela** | O Auto Router do OpenRouter (`openrouter/auto`) é medido no mesmo conjunto. |
| **Números honestos** | O README mostra também o que perdeu, intervalos de confiança e limites da medida. |
| **Decisão auditável** | Toda chamada grava o modelo escolhido, os descartados e o motivo. |

## Jev: medido, não promovido

O Jev está em alta. Aqui ele não é tratado como cérebro do gateway, e sim como mais um candidato que precisa
provar valor com números:

- **Primeiro resultado já na `v0.1.0`**; integração como política do gateway na V2.
- **Mesmo teste, mesma regra de decisão:** Jev Router × OpenRouter Auto × escada deste gateway × 13 modelos
  sozinhos, no conjunto de teste congelado.
- **Custo completo:** o que se paga ao Jev entra no custo por resposta correta.
- **Sem dependência cega:** se o Jev não responder no tempo-limite, a regra assume, e o gateway não para.
- **Resultado publicado em qualquer caso**, inclusive se o Jev perder.

Detalhes da decisão em [docs/adr/0004-jev-como-politica-plugavel.md](docs/adr/0004-jev-como-politica-plugavel.md).

## Resultados — v0.1.0 (conjunto de teste)

29 perguntas separadas, configuração congelada antes da rodada (tag `bench-v0-frozen`) e o mesmo
contexto de busca congelado para todos. Metodologia em [docs/BENCHMARK.md](docs/BENCHMARK.md).

| Alvo | Acerto | IC 95% | Custo / pergunta | Custo / resposta correta | Latência p50 / p95 |
|---|---|---|---|---|---|
| *Oráculo (limite teórico)* | 26/29 = 90% | 74–96% | US$ 0,0003 | US$ 0,0003 | — |
| DeepSeek V4 Pro (open) | 24/28 = 86% | 69–94% | US$ 0,0023 | US$ 0,0028 | 14,2 / 31,7 s |
| **GPT-6 Luna** | **24/29 = 83%** | 65–92% | **US$ 0,0007** | **US$ 0,0008** | **3,9 / 8,1 s** |
| OpenRouter Auto (`openrouter/auto`) | 24/29 = 83% | 65–92% | US$ 0,0010 | US$ 0,0013 | 6,0 / 15,1 s |
| Qwen 3.8 Flash (open) | 24/29 = 83% | 65–92% | US$ 0,0014 | US$ 0,0016 | 34,1 / 95,3 s |
| Qwen 3.8 27B (open) | 24/29 = 83% | 65–92% | US$ 0,0050 | US$ 0,0060 | 21,1 / 122,2 s |
| Gemini 3.8 Flash | 24/29 = 83% | 65–92% | US$ 0,0064 | US$ 0,0078 | 7,6 / 14,0 s |
| Nemotron 3 Super (open) | 23/29 = 79% | 62–90% | US$ 0,0007 | US$ 0,0008 | 23,0 / 57,3 s |
| Haiku 5.5 | 23/29 = 79% | 62–90% | US$ 0,0012 | US$ 0,0015 | 6,5 / 10,7 s |
| GLM 5.3 (open) | 23/29 = 79% | 62–90% | US$ 0,0045 | US$ 0,0057 | 7,5 / 22,6 s |
| DeepSeek V4.1 Flash (open) | 22/29 = 76% | 58–88% | US$ 0,0011 | US$ 0,0015 | 5,1 / 18,2 s |
| **Jev Router (`typesafe/jev-router`)** | 22/29 = 76% | 58–88% | US$ 0,0047 | US$ 0,0062 | 9,9 / 14,3 s |
| **Sonnet 5.5** | 21/29 = 72% | 54–85% | **US$ 0,0196** | **US$ 0,0271** | 9,3 / 13,0 s |
| Mistral Small (open, 25/29 respondidas) | 17/25 = 68% | 48–83% | US$ 0,0005 | US$ 0,0007 | 1,6 / 2,5 s |
| gpt-oss-120b (open) | 19/29 = 66% | 47–80% | US$ 0,0003 | US$ 0,0004 | 9,9 / 29,6 s |
| Llama 4 Maverick (open) | 19/29 = 66% | 47–80% | US$ 0,0006 | US$ 0,0010 | 6,4 / 14,0 s |

**Regra de decisão** (fixada antes do teste): menor custo por resposta correta entre as rotas a no máximo
5 pontos do melhor acerto → **GPT-6 Luna**: 83% (melhor: 86%) a **US$ 0,0008 por resposta correta,
34× mais barato que o Sonnet 5.5**, e o mais rápido do grupo de cima.

**O que a tabela mostra**
- O modelo caro padrão (Sonnet 5.5) não ganha: 72% a US$ 0,0271 por resposta correta.
- Modelos baratos e open source chegam ao grupo de cima (76–86%) por uma fração do custo.
- O OpenRouter Auto empatou com o grupo de cima (83%) por US$ 0,0013 por resposta correta; o Jev Router
  ficou em 76% a US$ 0,0062.
- O oráculo (o modelo mais barato que acertou cada pergunta) chega a 90% por US$ 0,0003: é o espaço que
  um router mais inteligente ainda pode capturar.

**Limites, sem rodeio**
- 29 perguntas: os intervalos de confiança se sobrepõem de 76% a 86%; diferenças dentro dessa faixa não
  são conclusivas. No conjunto de ajuste a ordem foi outra (lá o DeepSeek V4.1 Flash parecia o melhor).
- O acerto é decidido por um juiz LLM (Mistral Large 4, binário, comparando com o gabarito). **A
  conferência humana do juiz ainda está pendente**; os resultados serão atualizados se a concordância
  ficar abaixo de 85%.
- O gabarito foi escrito com IA e revisado pelo autor; a revisão por engenheiro de setup está pendente.
- A escada simulada nunca subiu de degrau: quase toda resposta cita fontes válidas mesmo quando erra,
  então a checagem de citação não detecta resposta errada. Uma checagem melhor para subir de degrau fica
  para a V2.
- Mistral Small: 4 respostas faltando (limite do provedor). Uma resposta (de 435) ficou sem veredito do juiz.
- Custo total da V0: **US$ 6,31** (respostas, juiz, teste rápido e congelamento da busca).

## Stack

Python 3.12 · FastAPI · Pydantic v2 · httpx (async) · PostgreSQL + SQLAlchemy 2 + Alembic · pgvector · Redis ·
Prometheus · Grafana · OpenTelemetry (convenções GenAI) · Docker Compose · GitHub Actions · pytest + respx ·
k6 · ruff · mypy · pre-commit · uv

## Desenvolvimento

Requer o [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # instala as dependências (Python 3.12)
cp .env.example .env         # preencha as chaves; o .env nunca vai para o git
uv run pytest                # testes offline (APIs pagas são simuladas)
uv run ruff check . && uv run mypy
uv run pre-commit install    # roda as checagens a cada commit
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/PLANO.md](docs/PLANO.md) | Plano do produto (fonte da verdade do escopo) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fases, releases, marcos, riscos e métricas de sucesso |
| [docs/SPRINTS.md](docs/SPRINTS.md) | Backlog por sprint com critérios de aceite |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Componentes, fluxo da requisição, modelo de dados, falhas |
| [docs/INFRA.md](docs/INFRA.md) | Ambientes, containers, VPS, CI/CD, segredos, backup |
| [docs/BENCHMARK.md](docs/BENCHMARK.md) | Metodologia de avaliação |
| [docs/adr/](docs/adr/) | Registro das decisões de arquitetura |
| [SECURITY.md](SECURITY.md) | Política de segurança e dados |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |

## Licença

[MIT](LICENSE)
