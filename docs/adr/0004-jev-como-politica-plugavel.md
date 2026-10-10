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

## Revisão (2026-10-10)
O Jev está disponível no OpenRouter como `typesafe/jev-router`: um router completo que escolhe o modelo e o nível
de raciocínio de cada pedido. Não há, pelo OpenRouter, um classificador de dificuldade separado. Por isso:
- **V0:** o Jev Router é medido como **router de mercado**, ao lado do `openrouter/auto`, na mesma tabela e com o
  mesmo contexto. A simulação "Jev escolhe o degrau inicial da escada" sai do plano.
- **V2:** a política Jev do gateway delega a escolha ao `typesafe/jev-router`, com tempo-limite e volta para a regra.
- Usa a mesma chave do OpenRouter; `TYPESAFE_API_KEY` deixa de ser necessária.
