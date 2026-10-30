from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(320), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ref_hash = Column(String, nullable=True, unique=True, index=True)
    exp_time = Column(DateTime(timezone=True), nullable=True)


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name = Column(String(200), nullable=False, index=True)
    contact_email = Column(String(320), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))


class ImportConfig(Base):
    __tablename__ = "import_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    config_data = Column(JSONB, nullable=False)


class SourceFile(Base):
    __tablename__ = "source_files"

    # Nullable only for files uploaded before supplier binding was introduced.
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    config_data: Mapped[dict | None] = mapped_column(JSONB)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    filename: Mapped[str] = mapped_column(String(255))

    object_key: Mapped[str] = mapped_column(
        String(512),
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="uploaded",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
