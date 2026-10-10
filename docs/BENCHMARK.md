# Metodologia de benchmark — llm-gateway

O benchmark é o produto principal: toda afirmação de economia no README vem daqui.

## Conjunto de dados

- **Fonte:** gabarito do iRacingEng (`data/rag/gabarito-v0.jsonl`), com 58 perguntas de engenharia de corrida
  (NASCAR Next Gen no iRacing).
- **Revisão:** respostas escritas com IA e revisadas pelo autor. A revisão por engenheiro de setup está
  **pendente**; cada tabela publicada informa quantas perguntas do conjunto de teste já foram revisadas por ele
  (campo `revisao.engenheiro`).
- **Privacidade:** o conjunto real tem trechos de manuais (direito autoral) e conhecimento da equipe. Ele fica
  **fora do git** e é lido de `BENCH_DATASET_PATH`. O repositório tem só o formato e um conjunto público de exemplo.
- **Divisão:** 29 perguntas de **ajuste** e 29 de **teste**, sorteadas com semente fixa e **estratificadas por
  categoria** (cada categoria dividida ao meio). Os IDs da divisão são versionados e não mudam.

## Regras de medição

1. Toda configuração (modelos, prompts, pisos, escada, juiz) é ajustada **só no conjunto de ajuste**.
2. Antes de rodar no teste, a configuração é **congelada** num commit com tag.
3. A tabela do README usa **só o conjunto de teste**.
4. Tudo é publicado, inclusive o que perdeu.

## Alvos medidos

| Alvo | Descrição |
|---|---|
| Modelos únicos | 16 modelos (lista e slugs em `docs/PLANO.md`, V0): 4 fechados de referência e 12 open source, incluindo 3 Qwen |
| `openrouter/auto` | Auto Router do OpenRouter; o modelo escolhido por pergunta é registrado |
| Jev Router | `typesafe/jev-router` (TypeSafe, pelo OpenRouter): escolhe modelo e nível de raciocínio; o modelo escolhido por pergunta é registrado |
| Escada com regra | Simulada sobre as respostas gravadas (V0) e medida ao vivo (V2) |
| Política Jev no gateway | V2: o gateway delega ao Jev Router, com tempo-limite e volta para a regra |
| Router aprendido | V3 |
| Oráculo | Para cada pergunta, o modelo mais barato que acertou. É o limite teórico |

## Contexto enviado aos modelos

O gabarito é de RAG: as respostas vêm de trechos de manuais e, nas perguntas de sessão, de dados da sessão.
Para medir a tarefa real do iRacingEng (e não a memória do modelo), todo modelo recebe **o mesmo contexto
congelado** (decisão de 2026-10-08):

- **Trechos:** a busca do próprio iRacingEng rodada uma vez no banco de staging (511 trechos de 12 manuais),
  top-8 por pergunta, em dois modos: **híbrido** (principal) e **com reordenação** (`cohere/rerank-v3.5`).
  Contexto realista, com acertos e erros: a página do gabarito aparece no top-8 em 39/47 perguntas no
  híbrido e 40/47 com reordenação. As perguntas sem resposta também recebem os trechos que a busca trouxe.
- **Números da sessão:** as perguntas de sessão recebem o bloco gerado pela ferramenta `ibt_info` do
  iRacingEng a partir do arquivo `.ibt` de Bristol (voltas, temperatura da pista, setup), sem cálculo nosso.
- **Privacidade:** trechos e números ficam fora do git (`bench/data/`). No repositório entram só os
  metadados e as assinaturas SHA-256 (`bench/results/context-freeze-*.json`).
- **Como foi gerado:** `bench/vps/run_freeze.sh` roda `bench/vps/freeze_retrieval.py` dentro do container de
  RAG do iRacingEng na VPS; a senha do banco não sai do servidor e o banco só é lido.

## Raciocínio e custo

- Cada modelo roda com o **raciocínio no padrão** dele (como seria usado de verdade). Os tokens de raciocínio são
  cobrados como saída; a tabela mostra quanto cada modelo gastou com eles.
- Teto da rodada completa: **US$ 8**. O script estima antes de rodar, mede o custo real a cada resposta e para
  sozinho se o teto for atingido.

## Avaliação

| Checagem | Tipo | O que verifica |
|---|---|---|
| Citação | Automática | A resposta cita a fonte exigida quando o gabarito pede |
| Recusa | Automática | O modelo não recusou nem fugiu da pergunta |
| Juiz binário | LLM com gabarito | Certo/errado comparando com a resposta esperada; modelo e prompt do juiz fixos |
| Amostra humana | Leandro | 10 respostas por modelo; mede a concordância com o juiz |

Uma resposta conta como **correta** quando passa nas checagens automáticas e o juiz aprova. A taxa de
concordância entre juiz e humano é publicada; se ficar abaixo de 85%, o juiz é revisto antes de publicar.

## Métricas

| Métrica | Definição |
|---|---|
| Acerto | corretas ÷ total, com intervalo de confiança de 95% (Wilson) |
| Custo por pergunta | soma de `usage.cost` ÷ total de perguntas, incluindo tentativas da escada |
| Custo por resposta correta | soma de `usage.cost` ÷ número de corretas |
| Latência p50 / p95 | Tempo total da chamada; na escada, soma das tentativas |

## Regra de decisão

Vale a rota de **menor custo por resposta correta entre as que ficam no máximo 5 pontos abaixo do melhor acerto**.

## Limites conhecidos

- Com 29 perguntas, cada pergunta vale ~3,4 pontos de acerto, e a margem de 5 pontos equivale a 1–2 perguntas.
  Diferenças pequenas devem ser lidas com o intervalo de confiança.
- Um único domínio: os resultados não se generalizam automaticamente para outras tarefas.
- Preços e modelos mudam. Cada tabela registra a data e a versão de cada modelo.

## Reprodutibilidade

- Respostas brutas gravadas localmente com modelo, provedor, data, tokens e custo.
- A escada e o oráculo são recalculados a partir das respostas gravadas, sem gastar de novo.
- Com o conjunto público de exemplo, qualquer pessoa roda o pipeline com a própria chave.
