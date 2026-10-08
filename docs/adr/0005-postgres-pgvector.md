# ADR 0005 — PostgreSQL com pgvector em vez de banco vetorial separado

**Status:** aceito · 2026-10-07

## Contexto
A V3 precisa de embeddings para o classificador por vizinhos mais próximos, e a V4 pode testar cache semântico.
A VPS tem 8 GB de RAM e é compartilhada.

## Decisão
Usar a extensão pgvector no mesmo PostgreSQL do registro de chamadas. A imagem `pgvector/pgvector` é usada desde a
V1 para não trocar de imagem depois.

## Consequências
- Um serviço a menos para operar, monitorar e fazer backup.
- Volume de dados pequeno (milhares de vetores), bem dentro do que o pgvector atende.
- Se o volume crescer muito, a decisão é revista.
