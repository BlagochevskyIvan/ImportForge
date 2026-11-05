from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
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
        index=True,
    )
    config_data = Column(JSONB, nullable=False)
    name: Mapped[str] = mapped_column(String(200), default="Основная", server_default="Основная")


class SourceFile(Base):
    __tablename__ = "source_files"

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'retry_wait', 'completed', 'failed')",
            name="ck_import_runs_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_import_runs_attempt_count"),
        Index(
            "uq_import_runs_active_file",
            "source_file_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing', 'retry_wait')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    source_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="RESTRICT"),
        index=True,
    )

    config_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_configs.id", ondelete="SET NULL"),
        index=True,
    )
    config_name: Mapped[str] = mapped_column(String(200))
    config_data: Mapped[dict] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        server_default="queued",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
    )

    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # счётчики, ключи артефактов/описание ошибки
    processing_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
