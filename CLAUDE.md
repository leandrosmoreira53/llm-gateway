# llm-gateway — CLAUDE.md

Este arquivo vale para este projeto e tem prioridade sobre qualquer `CLAUDE.md` de pastas acima
(o `Downloads/CLAUDE.md` é do yldlab-mcp e não se aplica aqui).

## Fontes da verdade

- Escopo: `docs/PLANO.md` · Sprint atual: `docs/SPRINTS.md` · Decisões: `docs/adr/`
- Mudou uma decisão? Novo ADR ou atualização do existente, no mesmo PR.

## Regras invioláveis

1. **Nada de gasto sem confirmação.** Antes de qualquer chamada paga (benchmark, teste live), mostrar a
   estimativa de custo e esperar o ok do Leandro.
2. **Testes nunca chamam API real.** OpenRouter e Jev simulados com `respx`. Testes reais só com
   `@pytest.mark.live`, manuais.
3. **Segredos só em `.env`.** Nunca em código, log, commit, issue ou resposta.
4. **Gabarito fora do git.** O conjunto real é lido de `BENCH_DATASET_PATH`; só resultados agregados são publicados.
5. **Benchmark honesto.** Ajuste só no conjunto de ajuste; congelar com tag antes de rodar no teste; publicar
   também o que perdeu.
6. **iRacingEng e VPS não são tocados** sem ok explícito do Leandro para aquela ação.
7. **Sem LiteLLM como proxy** (ADR 0003). O OpenRouter não escolhe o modelo (ADR 0002).
8. **O gateway não pode travar** se Redis, Postgres ou Jev caírem.

## Convenções

- Python 3.12, `uv`, layout `src/gateway/`, tipagem completa (`mypy --strict`), `ruff`.
- Código, nomes e mensagens de commit em inglês. `README.md` em inglês (padrão do GitHub), espelhado em
  `README.pt-BR.md`: toda mudança vale para os dois. Demais documentos em português.
- Commits no padrão Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Uma branch e um PR por tarefa `GW-x.y`; o PR cita o ID.
- Erros da API sempre no formato da OpenAI; nunca stack trace para o cliente.
- Toda chamada registra custo, modelo usado e motivo da rota.

## Comandos

```bash
uv sync
uv run pytest
uv run ruff check . && uv run mypy src
docker compose up -d
```
