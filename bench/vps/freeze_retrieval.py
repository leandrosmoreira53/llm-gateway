"""Freeze iRacingEng's retrieval for every benchmark question (decision 2a, 2026-10-08).

Runs INSIDE iRacingEng's `iracingeng-rag` container on the VPS (see run_freeze.sh), so the database
password never leaves the server. Read-only: it only SELECTs from the database; the paid calls are
OpenRouter query embeddings and, for the `rerank` mode, the re-ranker.

Writes one JSON document to stdout:
    {"meta": {...}, "questions": [{"id", "modes": {"hibrida": [hit...], "rerank": [hit...]}}],
     "chunks": {"<chunk_id>": {"source", "series", "page", "heading", "text"}}}

Standalone on purpose: it may import only the standard library, psycopg and iRacingEng's `rag`.
"""

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any

import psycopg
from rag import embed, rerank
from rag.search import GlossaryTerm, hybrid_search, rerank_search

MODES = ("hibrida", "rerank")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gabarito", required=True)
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--pool", type=int, default=20)
    parser.add_argument("--modes", default=",".join(MODES))
    args = parser.parse_args()
    modes = [m for m in args.modes.split(",") if m]
    if not set(modes) <= set(MODES):
        parser.error(f"modes must be in {MODES}")

    with open(args.gabarito, encoding="utf-8") as handle:
        questions = [json.loads(line) for line in handle if line.strip()]

    calls = {"embeddings": 0, "rerank": 0}
    out_questions: list[dict[str, Any]] = []
    chunk_ids: set[int] = set()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.read_only = True
        glossary = [
            GlossaryTerm(*row)
            for row in conn.execute("SELECT term, synonyms_pt, synonyms_en FROM kb.glossary")
        ]
        chunk_count = conn.execute("SELECT count(*) FROM kb.chunks").fetchone()[0]
        for n, q in enumerate(questions, 1):
            text = q["pergunta"]
            vec = embed.to_pgvector(embed.embed_query(text))
            calls["embeddings"] += 1
            result: dict[str, list[dict[str, Any]]] = {}
            for mode in modes:
                if mode == "hibrida":
                    hits = hybrid_search(conn, text, vec, glossary, args.k)
                else:
                    hits = rerank_search(conn, text, vec, glossary, args.k, args.pool)
                    calls["rerank"] += 1
                result[mode] = [{"chunk_id": h.chunk_id, "score": h.score} for h in hits]
                chunk_ids.update(h.chunk_id for h in hits)
            out_questions.append({"id": q["id"], "modes": result})
            print(f"{n}/{len(questions)} {q['id']}", file=sys.stderr)

        rows = conn.execute(
            """
            SELECT c.id, d.source, c.series, c.page, c.heading_path, c.text
            FROM kb.chunks c JOIN kb.documents d ON d.id = c.document_id
            WHERE c.id = ANY(%s)
            """,
            (sorted(chunk_ids),),
        ).fetchall()

    chunks = {
        str(cid): {"source": src, "series": ser, "page": page, "heading": head, "text": txt}
        for cid, src, ser, page, head, txt in rows
    }
    meta = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "environment": "staging",
        "image": os.environ.get("IRACINGENG_RAG_IMAGE"),
        "embed_model": embed.model(),
        "rerank_model": rerank.model(),
        "k": args.k,
        "pool": args.pool,
        "modes": modes,
        "query_language": "pt",
        "kb_chunks": chunk_count,
        "glossary_terms": len(glossary),
        "questions": len(questions),
        "paid_calls": calls,
    }
    json.dump(
        {"meta": meta, "questions": out_questions, "chunks": chunks}, sys.stdout, ensure_ascii=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
