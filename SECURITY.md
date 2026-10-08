# Segurança

## Como reportar uma vulnerabilidade

Não abra issue pública. Use o recurso "Report a vulnerability" (GitHub Security Advisories) deste repositório.
Resposta inicial em até 7 dias.

## O que o gateway guarda

| Dado | Guardado? |
|---|---|
| Custo, tokens, latência, modelo, motivo da rota | Sim |
| Hash da pergunta | Sim (usado no cache) |
| Texto da pergunta e da resposta | Não, por padrão; só com opção ligada e prazo de apagar |
| Chaves dos apps | Só como hash SHA-256 |
| Chaves de provedores (OpenRouter, TypeSafe) | Só em variável de ambiente; nunca em log ou banco |

## Práticas

- Segredos fora do git (`.env` ignorado; `.env.example` vazio).
- Testes e CI sem chaves reais.
- Dependências fixadas no `uv.lock`; atualização revisada por PR.
- Somente o gateway é exposto; banco, cache e métricas ficam na rede interna.
