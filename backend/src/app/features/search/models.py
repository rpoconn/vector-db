from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class ProductEmbedding(Base):
    """Cached document embedding of a product for one model.

    Deliberately no foreign key to `products`: re-seeding the same catalog keeps the cache, and
    `text_hash` detects products whose text changed.
    """

    __tablename__ = "product_embeddings"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    model: Mapped[str] = mapped_column(String(128), primary_key=True)
    text_hash: Mapped[str] = mapped_column(String(64))
    vector: Mapped[bytes] = mapped_column(LargeBinary)
