# ADR 0002 — OpenRouter como transporte, não como cérebro

**Status:** aceito · 2026-10-07

## Contexto
O OpenRouter dá acesso a muitos modelos com uma única chave e tem recursos próprios de roteamento: lista de
modelos reserva, preferência de provedor e o Auto Router (`openrouter/auto`), que escolhe o modelo sozinho.

## Decisão
- O **gateway escolhe o modelo**. Essa é a parte autoral do projeto.
- O OpenRouter escolhe **só o provedor** que serve o modelo escolhido (objeto `provider`) e aplica a lista de
  reservas (`models`) em caso de queda.
- O `openrouter/auto` **não é usado para rotear**. Ele entra no benchmark como concorrente.
- A interface `Provider` permite trocar o OpenRouter por APIs diretas (V4) sem mudar o resto.

## Consequências
- Uma chave e uma fatura na V0–V3; taxa de ~5,5% sobre os créditos.
- Dependência de um intermediário. Mitigada pela interface de provedor e pela volta do cliente para o OpenRouter
  direto quando o gateway cai.
