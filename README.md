# llm-gateway

**English** · [Português](README.pt-BR.md)

> An OpenAI-compatible LLM gateway that picks the model with the lowest **cost per correct answer**,
> and publishes a reproducible benchmark showing how much it saves (and where it doesn't).
> Benchmarks 13 models (closed and open source, including Qwen) and two market routers, **Jev Router** and
> OpenRouter Auto, on the same frozen test set.

**Status:** planning complete · Sprint 0 · next release: `v0.1.0` (benchmark), due 2026-10-25.

---

## The problem

LLM applications usually pin one expensive model for every call. Many requests would be answered correctly by
a model several times cheaper, but switching models on gut feeling puts quality at risk, and nobody measures
the outcome.

## The solution

A gateway that sits between applications and models:

1. Accepts requests in the OpenAI API format. Any client only changes its base URL.
2. Drops models that can't serve the request (context window, vision, tools, JSON mode).
3. Picks the model with the lowest **expected cost per correct answer**.
4. Calls it through OpenRouter, with fallback models and cheapest/fastest provider selection.
5. Checks the answer with objective validators. If a check fails, it climbs one step up the ladder (stronger model).
6. Logs everything: model, provider, tokens, cost, latency, checks, ladder step, and **why** the route was chosen.

```
 Apps (iRacingEng, ...) ──► POST /v1/chat/completions  (model: "auto-engenheiro")
                                  │
            ┌──────────────── llm-gateway ────────────────┐
            │ auth + budget + rate limit                  │
            │ capability filter                           │
            │ routing policy (rule │ Jev │ learned)       │
            │ exact cache                                 │
            │ validated ladder ──► escalate on failure    │
            │ auditable log (Postgres)                    │
            └──────────────────┬──────────────────────────┘
                               ▼
                          OpenRouter ──► Claude · GPT · Gemini · DeepSeek · ...
```

## Highlights

| | |
|---|---|
| **Proven savings** | Every release publishes a "router vs. single model" table with accuracy, cost per correct answer and latency, measured on a held-out, frozen test set. |
| **Validated ladder** | Cheap model first; escalate to the expensive one only when an objective check fails. |
| **Real-domain benchmark** | 58 race-engineering questions (NASCAR Next Gen in iRacing), including trick questions and questions with no answer in the sources. The answer key was drafted with AI and reviewed by the author; review by a setup engineer is pending and will be reported when done. |
| **Jev beyond the hype** | TypeSafe's Jev Router (`typesafe/jev-router`) picks a model and reasoning effort per request. It is measured head-to-head on the same questions and context, with its full cost. In V2 it can plug into the gateway as an alternative policy, with a timeout that falls back to the rule; it becomes the main policy only if it wins on the test set. |
| **Market baseline in the table** | OpenRouter's Auto Router (`openrouter/auto`) is measured on the same set. |
| **Honest numbers** | The README also reports what lost, confidence intervals and the limits of the measurement. |
| **Auditable decisions** | Every call records the chosen model, the rejected ones and the reason. |

## Jev: measured, not promoted

Jev is getting a lot of attention. Here it is not the gateway's brain, just another candidate that has to prove
its value with numbers:

- **First result in `v0.1.0`**; integration as a gateway policy in V2.
- **Same test, same decision rule:** Jev Router vs. OpenRouter Auto vs. this gateway's ladder vs. 13 single models, on the frozen test set.
- **Full cost:** what Jev charges is included in the cost per correct answer.
- **No blind dependency:** if Jev doesn't answer within the timeout, the rule takes over and the gateway keeps running.
- **Result published either way**, including if Jev loses.

Decision record (Portuguese): [docs/adr/0004-jev-como-politica-plugavel.md](docs/adr/0004-jev-como-politica-plugavel.md).

## Results

> Published starting at `v0.1.0`. Methodology (Portuguese): [docs/BENCHMARK.md](docs/BENCHMARK.md).

| Target | Accuracy | Cost per question | Cost per correct answer | Latency p50 / p95 |
|---|---|---|---|---|
| Sonnet 5.5 alone | — | — | — | — |
| Cheapest model alone | — | — | — | — |
| Best single model | — | — | — | — |
| OpenRouter Auto (`openrouter/auto`) | — | — | — | — |
| Jev Router (`typesafe/jev-router`) | — | — | — | — |
| Ladder with rule | — | — | — | — |
| Learned router | — | — | — | — |
| Oracle (theoretical bound) | — | — | — | — |

## Stack

Python 3.12 · FastAPI · Pydantic v2 · httpx (async) · PostgreSQL + SQLAlchemy 2 + Alembic · pgvector · Redis ·
Prometheus · Grafana · OpenTelemetry (GenAI semantic conventions) · Docker Compose · GitHub Actions ·
pytest + respx · k6 · ruff · mypy · pre-commit · uv

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install Python 3.12 deps
cp .env.example .env         # fill in keys; never commit .env
uv run pytest                # offline tests (paid APIs are mocked)
uv run ruff check . && uv run mypy
uv run pre-commit install    # run checks on every commit
```

## Documentation

Detailed documents are in Portuguese.

| Document | Contents |
|---|---|
| [docs/PLANO.md](docs/PLANO.md) | Product plan (source of truth for scope) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases, releases, milestones, risks and success metrics |
| [docs/SPRINTS.md](docs/SPRINTS.md) | Sprint backlog with acceptance criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request flow, data model, failure modes |
| [docs/INFRA.md](docs/INFRA.md) | Environments, containers, VPS, CI/CD, secrets, backups |
| [docs/BENCHMARK.md](docs/BENCHMARK.md) | Evaluation methodology |
| [docs/adr/](docs/adr/) | Architecture decision records |
| [SECURITY.md](SECURITY.md) | Security and data policy |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## License

[MIT](LICENSE)
