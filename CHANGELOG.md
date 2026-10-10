# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem
[SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.1.0] - 2026-10-10

Benchmark V0: 13 modelos e 2 routers de mercado nas 58 perguntas do iRacingEng (29 de ajuste, 29 de teste),
com contexto congelado e juiz LLM. Resultado: GPT-6 Luna vence pela regra de decisão (83%, US$ 0,0008 por
resposta correta, 34× mais barato que o Sonnet 5.5). Conferência humana do juiz pendente.

### Adicionado
- Executor do benchmark com estimativa de custo, teto e retomada (GW-2.1); juiz binário e validadores de
  citação e recusa (GW-2.2, GW-2.3); planilha cega de revisão humana (GW-2.4); tabela com escada simulada,
  oráculo e intervalo de confiança (GW-2.5, GW-2.7).
- Jev Router e OpenRouter Auto medidos como routers de mercado (GW-2.6).
- Tabela de resultados no README.

### Corrigido
- O `.env` do projeto passa a ter prioridade sobre uma `OPENROUTER_API_KEY` global da máquina.
- Juiz com raciocínio baixo, para não estourar o limite de tokens antes do veredito.

### Adicionado (planejamento e fundação)
- Plano do produto, roadmap, sprints, arquitetura, infraestrutura, metodologia de benchmark e ADRs 0001–0005.
- Jev medido já na V0, pelo OpenRouter (`typesafe/jev-router`).
- Licença MIT.
- README em inglês como padrão (`README.md`); versão em português em `README.pt-BR.md`.
- Esqueleto do projeto (uv, ruff, mypy, pytest, pre-commit) e CI no GitHub Actions (GW-1.1, 1.2, 1.6).
- Cliente do OpenRouter com custo, tokens, latência, reservas e erros tipados (GW-1.3).
- Formato do gabarito em JSONL, exemplo público e divisão ajuste/teste congelada (GW-1.4, 1.5).
- Leitor do gabarito do iRacingEng e divisão estratificada por categoria (GW-1.5).
- Contexto congelado do benchmark: busca do iRacingEng (híbrida e com reordenação) e números da sessão de Bristol (GW-2.0).
