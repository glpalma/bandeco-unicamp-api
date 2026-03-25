from datetime import date, datetime
from typing import Optional
from sqlmodel import Field, SQLModel, UniqueConstraint
from app.config import BRASILIA_TZ


class CardapioBase(SQLModel):
    data: date = Field(index=True)
    refeicao: str = Field(description="'almoco' or 'jantar'")
    tipo: str = Field(description="'regular' or 'vegano'")
    prato_principal: Optional[str] = None
    arroz_feijao: Optional[str] = None
    guarnicao: Optional[str] = None
    salada: Optional[str] = None
    sobremesa: Optional[str] = None
    suco: Optional[str] = None
    observacoes: Optional[str] = None


class Cardapio(CardapioBase, table=True):
    __table_args__ = (
        UniqueConstraint("data", "refeicao", "tipo", name="uq_data_refeicao_tipo"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(BRASILIA_TZ)
    )


# ── Response schemas ────────────────────────────────────────────────────────

class ItemRefeicao(SQLModel):
    prato_principal: Optional[str] = None
    arroz_feijao: Optional[str] = None
    guarnicao: Optional[str] = None
    salada: Optional[str] = None
    sobremesa: Optional[str] = None
    suco: Optional[str] = None
    observacoes: Optional[str] = None


class RefeicaoResponse(SQLModel):
    regular: Optional[ItemRefeicao] = None
    vegano: Optional[ItemRefeicao] = None


class CardapioResponse(SQLModel):
    data: date
    last_updated: datetime
    almoco: Optional[RefeicaoResponse] = None
    jantar: Optional[RefeicaoResponse] = None


class DatasDisponiveisResponse(SQLModel):
    datas: list[date]
