### Resultados — v0-test

| Alvo | Acerto | IC 95% | Custo/pergunta | Custo/resp. correta | Latência p50 / p95 |
|---|---|---|---|---|---|
| Oráculo (mais barato que acertou) | 26/29 = 90% | 74%–96% | $0.0003 | $0.0003 | — |
| deepseek/deepseek-v4-pro | 24/28 = 86% | 69%–94% | $0.0023 | $0.0028 | 14.2s / 31.7s |
| Escada: gpt-6-luna → deepseek-v4-pro | 24/29 = 83% | 65%–92% | $0.0007 | $0.0008 | 3.9s / 8.1s |
| openai/gpt-6-luna | 24/29 = 83% | 65%–92% | $0.0007 | $0.0008 | 3.9s / 8.1s |
| openrouter/auto | 24/29 = 83% | 65%–92% | $0.0010 | $0.0013 | 6.0s / 15.1s |
| qwen/qwen3.8-flash | 24/29 = 83% | 65%–92% | $0.0014 | $0.0016 | 34.1s / 95.3s |
| qwen/qwen3.8-27b | 24/29 = 83% | 65%–92% | $0.0050 | $0.0060 | 21.1s / 122.2s |
| google/gemini-3.8-flash | 24/29 = 83% | 65%–92% | $0.0064 | $0.0078 | 7.6s / 14.0s |
| nvidia/nemotron-3-super-120b-a12b | 23/29 = 79% | 62%–90% | $0.0007 | $0.0008 | 23.0s / 57.3s |
| anthropic/claude-haiku-5.5 | 23/29 = 79% | 62%–90% | $0.0012 | $0.0015 | 6.5s / 10.7s |
| z-ai/glm-5.3 | 23/29 = 79% | 62%–90% | $0.0045 | $0.0057 | 7.5s / 22.6s |
| deepseek/deepseek-v4.1-flash | 22/29 = 76% | 58%–88% | $0.0011 | $0.0015 | 5.1s / 18.2s |
| typesafe/jev-router | 22/29 = 76% | 58%–88% | $0.0047 | $0.0062 | 9.9s / 14.3s |
| anthropic/claude-sonnet-5.5 | 21/29 = 72% | 54%–85% | $0.0196 | $0.0271 | 9.3s / 13.0s |
| mistralai/mistral-small-2603 (25 resp.) | 17/25 = 68% | 48%–83% | $0.0005 | $0.0007 | 1.6s / 2.5s |
| openai/gpt-oss-120b | 19/29 = 66% | 47%–80% | $0.0003 | $0.0004 | 9.9s / 29.6s |
| meta-llama/llama-4-maverick | 19/29 = 66% | 47%–80% | $0.0006 | $0.0010 | 6.4s / 14.0s |
