# Metodologia de benchmark — llm-gateway

O benchmark é o produto principal: toda afirmação de economia no README vem daqui.

## Conjunto de dados

- **Fonte:** gabarito do iRacingEng, com 58 perguntas de engenharia de corrida (NASCAR no iRacing) e respostas
  revisadas por engenheiro de setup.
- **Privacidade:** o conjunto real tem trechos de manuais (direito autoral) e conhecimento da equipe. Ele fica
  **fora do git** e é lido de `BENCH_DATASET_PATH`. O repositório tem só o formato e um conjunto público de exemplo.
- **Divisão:** 29 perguntas de **ajuste** e 29 de **teste**, sorteadas com semente fixa. Os IDs da divisão são
  versionados e não mudam.

## Regras de medição

1. Toda configuração (modelos, prompts, pisos, escada, juiz) é ajustada **só no conjunto de ajuste**.
2. Antes de rodar no teste, a configuração é **congelada** num commit com tag.
3. A tabela do README usa **só o conjunto de teste**.
4. Tudo é publicado, inclusive o que perdeu.

## Alvos medidos

| Alvo | Descrição |
|---|---|
| Modelos únicos | Sonnet 5.5, Haiku 5.5, Gemini 3.8 Flash, GPT-5.6 Luna, DeepSeek V4.1 Flash |
| `openrouter/auto` | Auto Router do OpenRouter; o modelo escolhido por pergunta é registrado |
| Escada com regra | Simulada sobre as respostas gravadas (V0) e medida ao vivo (V2) |
| Escada com Jev | O Jev classifica a dificuldade e escolhe o degrau inicial. Simulada na V0 (mapa dificuldade → degrau ajustado só no conjunto de ajuste), ao vivo na V2. O custo do Jev entra na conta |
| Router aprendido | V3 |
| Oráculo | Para cada pergunta, o modelo mais barato que acertou. É o limite teórico |

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
