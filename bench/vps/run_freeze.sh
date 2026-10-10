#!/usr/bin/env bash
# Runs freeze_retrieval.py inside iRacingEng's RAG image against the STAGING database, the same way
# iRacingEng's deploy/rag/rag.sh does: the DATABASE_URL and keys are read from the environment's .env
# into a temporary 600 file and never printed. Read-only on the database.
#
# Usage on the VPS (as deploy):  bash run_freeze.sh /tmp/llmgw/freeze_retrieval.py > snapshot.json
set -euo pipefail

SCRIPT="${1:?usage: run_freeze.sh <path/to/freeze_retrieval.py> [args]}"
shift
BASE="${IRACINGENG_BASE_DIR:-/opt/iracingeng}"
ENV_NAME=staging
IMAGE=iracingeng-rag
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "image $IMAGE missing" >&2; exit 1; }

envfile="$(mktemp)"
chmod 600 "$envfile"
trap 'rm -f "$envfile"' EXIT
val() { sed -n "s/^$1=//p" "$BASE/$ENV_NAME/.env" | tail -n 1; }
{
  echo "DATABASE_URL=postgresql://$(val POSTGRES_USER):$(val POSTGRES_PASSWORD)@db:5432/$(val POSTGRES_DB)"
  for k in OPENROUTER_API_KEY RAG_EMBED_MODEL RAG_RERANK_MODEL; do
    v="$(val "$k")"; [ -n "$v" ] && echo "$k=$v"
  done
  echo "IRACINGENG_RAG_IMAGE=$(docker image inspect "$IMAGE" --format '{{.Id}}' | cut -c8-19)"
} > "$envfile"

docker run --rm --network "iracingeng-${ENV_NAME}_default" --env-file "$envfile" \
  -v "$SCRIPT:/freeze_retrieval.py:ro" -v "$BASE/dados/rag:/dados/rag:ro" \
  --entrypoint python "$IMAGE" /freeze_retrieval.py --gabarito /dados/rag/gabarito-v0.jsonl "$@"
