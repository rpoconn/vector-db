from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    brand: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(128))
    price_cents: Mapped[int]
    source_url: Mapped[str] = mapped_column(String(256))

    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        order_by="ProductImage.position",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (UniqueConstraint("product_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    position: Mapped[int]
    path: Mapped[str] = mapped_column(String(256))
    width: Mapped[int]
    height: Mapped[int]

    product: Mapped[Product] = relationship(back_populates="images", lazy="raise")
