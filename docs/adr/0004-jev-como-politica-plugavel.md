# ADR 0004 — Jev como política plugável

**Status:** aceito · 2026-10-07

## Contexto
O Jev (TypeSafe) classifica a dificuldade da pergunta e poderia escolher o degrau inicial da escada. É uma API
fechada e paga; se ela cair, o gateway não pode parar.

## Decisão
O Jev é uma implementação da interface `Policy`, ao lado da regra. Tem tempo-limite; sem resposta, vale a regra.
O custo do Jev é somado ao custo da chamada. Ele vira a política principal só se ganhar da regra no conjunto de teste.

## Consequências
- O resultado do Jev, bom ou ruim, entra na tabela do README.
- O primeiro número sai na V0, por simulação sobre as respostas gravadas (custo de centavos). A integração ao
  vivo vem na V2, e o resultado ao vivo é comparado com o simulado.
- Exige `TYPESAFE_API_KEY` a partir da V0.
