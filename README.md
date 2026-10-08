# llm-gateway

**Português** · [English](README.en.md)

> Gateway de LLM compatível com a API da OpenAI que escolhe o modelo pelo **custo por resposta correta**
> e publica, com benchmark reproduzível, quanto economiza (e onde não economiza).
> Inclui o **Jev** como política de rota plugável, medido lado a lado com a regra no mesmo conjunto de teste.

**Status:** planejamento concluído · Sprint 0 · próxima entrega: `v0.1.0` (benchmark), fim de 25/10/2026.

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
| **Benchmark de domínio real** | Perguntas de engenharia de corrida (NASCAR no iRacing) com gabarito revisado por engenheiro de setup. |
| **Jev fora do hype, dentro do projeto** | O Jev classifica a dificuldade da pergunta e escolhe o degrau inicial da escada. Entra como política plugável, com tempo-limite e volta para a regra se não responder, e com o próprio custo somado ao da chamada. Só vira a política principal se ganhar no conjunto de teste. |
| **Concorrente de mercado na tabela** | O Auto Router do OpenRouter (`openrouter/auto`) é medido no mesmo conjunto. |
| **Números honestos** | O README mostra também o que perdeu, intervalos de confiança e limites da medida. |
| **Decisão auditável** | Toda chamada grava o modelo escolhido, os descartados e o motivo. |

## Jev: medido, não promovido

O Jev está em alta. Aqui ele não é tratado como cérebro do gateway, e sim como mais um candidato que precisa
provar valor com números:

- **Primeiro resultado já na `v0.1.0`** (simulação sobre as respostas gravadas); integração ao vivo na V2.
- **Mesmo teste, mesma regra de decisão:** escada com Jev × escada com regra × Sonnet sozinho, no conjunto de
  teste congelado.
- **Custo completo:** o que se paga ao Jev entra no custo por resposta correta.
- **Sem dependência cega:** se o Jev não responder no tempo-limite, a regra assume, e o gateway não para.
- **Resultado publicado em qualquer caso**, inclusive se o Jev perder.

Detalhes da decisão em [docs/adr/0004-jev-como-politica-plugavel.md](docs/adr/0004-jev-como-politica-plugavel.md).

## Resultados

> Publicados a partir da `v0.1.0`. Metodologia em [docs/BENCHMARK.md](docs/BENCHMARK.md).

| Alvo | Acerto | Custo por pergunta | Custo por resposta correta | Latência p50 / p95 |
|---|---|---|---|---|
| Sonnet 5.5 sozinho | — | — | — | — |
| Modelo mais barato sozinho | — | — | — | — |
| Melhor modelo único | — | — | — | — |
| OpenRouter Auto (`openrouter/auto`) | — | — | — | — |
| Escada com regra | — | — | — | — |
| Escada com Jev | — | — | — | — |
| Router aprendido | — | — | — | — |
| Oráculo (limite teórico) | — | — | — | — |

## Stack

Python 3.12 · FastAPI · Pydantic v2 · httpx (async) · PostgreSQL + SQLAlchemy 2 + Alembic · pgvector · Redis ·
Prometheus · Grafana · OpenTelemetry (convenções GenAI) · Docker Compose · GitHub Actions · pytest + respx ·
k6 · ruff · mypy · pre-commit · uv

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
