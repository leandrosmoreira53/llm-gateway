# ADR 0003 — Sem LiteLLM na frente

**Status:** aceito · 2026-10-07

## Contexto
O LiteLLM já oferece proxy compatível com a OpenAI, fallbacks, orçamento e cache.

## Decisão
O gateway é código próprio. O LiteLLM pode entrar apenas como biblioteca auxiliar (tabelas de preço e contagem
de tokens), se ajudar.

## Consequências
- Mais código a escrever e manter.
- A política de rota, a escada com checagem e o registro auditável, que são o diferencial do projeto, ficam
  visíveis e testáveis, em vez de escondidos numa configuração de terceiros.
