"""Adapters from external answer-key formats to the benchmark `Question` model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bench.dataset import Question


class IRacingEngSource(BaseModel):
    """A manual excerpt (doc/arquivo/serie/pagina/trecho) or a session datum (sessao/dado/valor)."""

    model_config = ConfigDict(extra="forbid")

    doc: str
    arquivo: str | None = None
    serie: str | None = None
    pagina: int | None = None
    trecho: str | None = None
    sessao: str | None = None
    dado: str | None = None
    valor: str | None = None

    def label(self) -> str:
        if self.pagina is not None:
            return f"{self.doc} p.{self.pagina}"
        return self.doc


class IRacingEngReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leandro: str | None = None
    data: str | None = None
    engenheiro: str | None = None


class IRacingEngRow(BaseModel):
    """One line of iRacingEng's `data/rag/gabarito-v0.jsonl`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    categoria: str
    pergunta: str
    pergunta_en: str | None = None
    filtros: dict[str, str] = Field(default_factory=dict)
    resposta_esperada: str
    fontes: list[IRacingEngSource] = Field(default_factory=list)
    armadilha: str | None = None
    sem_resposta: bool = False
    autor: str | None = None
    revisao: IRacingEngReview = Field(default_factory=IRacingEngReview)


def is_iracingeng_row(raw: dict[str, Any]) -> bool:
    return "pergunta" in raw and "resposta_esperada" in raw


def from_iracingeng(raw: dict[str, Any]) -> Question:
    row = IRacingEngRow.model_validate(raw)
    return Question(
        id=row.id,
        question=row.pergunta,
        question_en=row.pergunta_en,
        expected_answer=row.resposta_esperada,
        # A question without an answer in the sources is answered correctly by saying so.
        no_answer=row.sem_resposta,
        citation_required=bool(row.fontes) and not row.sem_resposta,
        expected_sources=[source.label() for source in row.fontes],
        gold_sources=[(source.arquivo or source.doc, source.pagina) for source in row.fontes],
        source_passages=[
            source.trecho if source.trecho else f"{source.sessao}: {source.dado} = {source.valor}"
            for source in row.fontes
        ],
        trap=row.armadilha,
        filters=row.filtros,
        category=row.categoria,
        engineer_reviewed=bool(row.revisao.engenheiro),
    )
