# ADR 0001 — Benchmark antes do gateway

**Status:** aceito · 2026-10-07

## Contexto
O valor do projeto depende de uma hipótese: rotear entre modelos reduz o custo por resposta correta sem perder
qualidade relevante. Construir o gateway antes de testar a hipótese arrisca semanas de trabalho sem ganho.

## Decisão
A V0 é só o benchmark: 5 modelos, `openrouter/auto` e escada simulada sobre respostas gravadas, com custo
estimado de US$ 4–7. O gateway só começa com a tabela publicada.

## Consequências
- A regra inicial da V1 usa números medidos, não suposições.
- Se rotear não valer a pena, o resultado é publicado e o escopo é revisto.
- O benchmark vira o produto central do README.
