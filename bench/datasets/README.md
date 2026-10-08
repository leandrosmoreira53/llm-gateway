# Conjuntos de dados do benchmark

O gabarito real do iRacingEng **não fica neste repositório** (contém trechos de manuais e conhecimento da
equipe). Ele é lido do caminho em `BENCH_DATASET_PATH`. Aqui ficam só o formato, um exemplo público e o
arquivo de divisão (`split.json`, apenas IDs).

## Formato (JSONL, uma pergunta por linha)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `id` | texto (`A-Z a-z 0-9 _ . -`) | sim | Identificador único e estável |
| `question` | texto | sim | Pergunta enviada ao modelo |
| `expected_answer` | texto | sim | Resposta esperada, usada pelo juiz |
| `context` | texto | não | Contexto extra enviado junto (carro, pista, valores de setup) |
| `citation_required` | booleano | não (padrão `false`) | Se a resposta precisa citar fonte |
| `expected_sources` | lista de texto | se `citation_required` | Fontes que a resposta deve citar |
| `category` | texto | não | Tema (balanço, pneus, freios...) para análise por categoria |

Campos desconhecidos são rejeitados, para pegar erros de digitação.

## Exemplo público

[`example.jsonl`](example.jsonl) tem 6 perguntas genéricas de dinâmica veicular, escritas para este
repositório (sem trechos de manuais). Serve para rodar o pipeline sem o gabarito real.

## Divisão ajuste/teste

```bash
uv run python -m bench.split --dataset "$BENCH_DATASET_PATH" --out bench/datasets/split.json
```

- Semente fixa (`20261012`); metade arredondada para baixo vai para ajuste, o resto para teste.
- O arquivo guarda o SHA-256 do gabarito. Se o gabarito mudar, o carregamento da divisão falha de propósito.
- Uma divisão existente não é sobrescrita: ela é congelada.
