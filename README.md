# llm-gateway

**English** · [Português](README.pt-BR.md)

> An OpenAI-compatible LLM gateway that picks the model with the lowest **cost per correct answer**,
> and publishes a reproducible benchmark showing how much it saves (and where it doesn't).
> Benchmarks 13 models (closed and open source, including Qwen) and two market routers, **Jev Router** and
> OpenRouter Auto, on the same frozen test set.

**Status:** `v0.1.0` — benchmark published (see [Results](#results--v010-test-set)). Next: V1, the gateway itself.

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

## Results — v0.1.0 (test set)

29 held-out questions, configuration frozen before the run (git tag `bench-v0-frozen`), same frozen
retrieval context for every target. Methodology (Portuguese): [docs/BENCHMARK.md](docs/BENCHMARK.md).

| Target | Accuracy | 95% CI | Cost / question | Cost / correct answer | Latency p50 / p95 |
|---|---|---|---|---|---|
| *Oracle (theoretical bound)* | 26/29 = 90% | 74–96% | $0.0003 | $0.0003 | — |
| DeepSeek V4 Pro (open) | 24/28 = 86% | 69–94% | $0.0023 | $0.0028 | 14.2 / 31.7 s |
| **GPT-6 Luna** | **24/29 = 83%** | 65–92% | **$0.0007** | **$0.0008** | **3.9 / 8.1 s** |
| OpenRouter Auto (`openrouter/auto`) | 24/29 = 83% | 65–92% | $0.0010 | $0.0013 | 6.0 / 15.1 s |
| Qwen 3.8 Flash (open) | 24/29 = 83% | 65–92% | $0.0014 | $0.0016 | 34.1 / 95.3 s |
| Qwen 3.8 27B (open) | 24/29 = 83% | 65–92% | $0.0050 | $0.0060 | 21.1 / 122.2 s |
| Gemini 3.8 Flash | 24/29 = 83% | 65–92% | $0.0064 | $0.0078 | 7.6 / 14.0 s |
| Nemotron 3 Super (open) | 23/29 = 79% | 62–90% | $0.0007 | $0.0008 | 23.0 / 57.3 s |
| Haiku 5.5 | 23/29 = 79% | 62–90% | $0.0012 | $0.0015 | 6.5 / 10.7 s |
| GLM 5.3 (open) | 23/29 = 79% | 62–90% | $0.0045 | $0.0057 | 7.5 / 22.6 s |
| DeepSeek V4.1 Flash (open) | 22/29 = 76% | 58–88% | $0.0011 | $0.0015 | 5.1 / 18.2 s |
| **Jev Router (`typesafe/jev-router`)** | 22/29 = 76% | 58–88% | $0.0047 | $0.0062 | 9.9 / 14.3 s |
| **Sonnet 5.5** | 21/29 = 72% | 54–85% | **$0.0196** | **$0.0271** | 9.3 / 13.0 s |
| Mistral Small (open, 25/29 answered) | 17/25 = 68% | 48–83% | $0.0005 | $0.0007 | 1.6 / 2.5 s |
| gpt-oss-120b (open) | 19/29 = 66% | 47–80% | $0.0003 | $0.0004 | 9.9 / 29.6 s |
| Llama 4 Maverick (open) | 19/29 = 66% | 47–80% | $0.0006 | $0.0010 | 6.4 / 14.0 s |

**Decision rule** (fixed before the test run): lowest cost per correct answer among routes within
5 points of the best accuracy → **GPT-6 Luna**: 83% (best: 86%) at **$0.0008 per correct answer,
34× cheaper than Sonnet 5.5**, and the fastest of the top group.

**What it shows**
- The expensive default (Sonnet 5.5) does not win: 72% at $0.0271 per correct answer.
- Cheap and open-weight models reach the top cluster (76–86%) at a fraction of the cost.
- OpenRouter Auto matched the top group (83%) for $0.0013 per correct answer; Jev Router reached 76% at
  $0.0062.
- The oracle (cheapest model that got each question right) reaches 90% at $0.0003: the room a smarter
  router could still capture.

**Limits, stated plainly**
- 29 questions: confidence intervals overlap from 76% to 86%; differences inside that band are not
  conclusive. On the tune set the order changed (DeepSeek V4.1 Flash looked best there).
- Correctness is decided by an LLM judge (Mistral Large 4, binary, against the answer key). **The human
  check of the judge is still pending**; results will be updated if agreement is below 85%.
- The answer key was drafted with AI and reviewed by the author; setup-engineer review is pending.
- The simulated ladder never escalated: almost every answer cites valid sources even when wrong, so a
  citation check does not detect wrong answers. A better escalation check is V2 work.
- Mistral Small: 4 answers missing (provider rate limits). One answer (out of 435) had no judge verdict.
- Whole V0 cost: **US$ 6.31** (answers, judge, smoke test and retrieval freeze).

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
