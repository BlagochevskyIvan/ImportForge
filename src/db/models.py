from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(320), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
