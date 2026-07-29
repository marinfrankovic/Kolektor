from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import JSON as GenericJSON
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Production runs on PostgreSQL; the SQLite variants exist so the test suite needs no server.
JSONType = JSONB().with_variant(GenericJSON(), "sqlite")
StringArray = ARRAY(String(60)).with_variant(GenericJSON(), "sqlite")
PgUUID = Uuid(as_uuid=True)

UI_LANGUAGES = ("en", "hr")
AUTH_MODES = ("password", "open")

ITEM_KINDS = ("coin", "banknote", "token", "set", "other")
ITEM_STATUSES = (
    "owned",
    "wish",
    "ordered",
    "duplicate",
    "for_sale",
    "sold",
    "missing",
)
IMAGE_ROLES = (
    "obverse",
    "reverse",
    "face",
    "back",
    "edge",
    "watermark",
    "detail",
    "certificate",
    "other",
)
IMAGE_STATUSES = ("pending", "processing", "ready", "failed")
JOB_STATUSES = ("queued", "running", "done", "failed")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class InstanceConfig(Base):
    """Single row. `open` mode drops the login screen for LAN-only installs."""

    __tablename__ = "instance_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_instance_config_singleton"),
        CheckConstraint(f"auth_mode IN {AUTH_MODES}", name="ck_instance_auth_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    auth_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="password")
    setup_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    """Kolektor is deliberately single-user; a second row is rejected at the service layer."""

    __tablename__ = "user_account"
    __table_args__ = (CheckConstraint(f"language IN {UI_LANGUAGES}", name="ck_user_language"),)

    id: Mapped[uuid.UUID] = mapped_column(PgUUID, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionToken(Base):
    __tablename__ = "session_token"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(400))


class Country(Base):
    __tablename__ = "country"

    code2: Mapped[str] = mapped_column(String(2), primary_key=True)
    code3: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    numeric3: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    continent: Mapped[str | None] = mapped_column(String(40))


class HistoricalEntity(Base):
    """Defunct issuers mapped onto a present-day territory so the world map can colour them."""

    __tablename__ = "historical_entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    successor_code2: Mapped[str | None] = mapped_column(String(2), ForeignKey("country.code2"))
    from_year: Mapped[int | None] = mapped_column(Integer)
    to_year: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class Item(Base, TimestampMixin):
    __tablename__ = "item"
    __table_args__ = (
        CheckConstraint(f"kind IN {ITEM_KINDS}", name="ck_item_kind"),
        CheckConstraint(f"status IN {ITEM_STATUSES}", name="ck_item_status"),
        CheckConstraint("quantity >= 0", name="ck_item_quantity"),
        Index("ix_item_country_kind", "map_country_code", "kind"),
        Index("ix_item_year", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID, primary_key=True, default=_uuid)

    # Mandatory core.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="owned")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Identity.
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("country.code2"))
    map_country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("country.code2"), index=True)
    issuing_entity: Mapped[str | None] = mapped_column(String(160))
    region: Mapped[str | None] = mapped_column(String(120))
    period: Mapped[str | None] = mapped_column(String(160))
    ruler: Mapped[str | None] = mapped_column(String(160))

    denomination_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    denomination_text: Mapped[str | None] = mapped_column(String(60))
    currency_unit: Mapped[str | None] = mapped_column(String(60))

    year: Mapped[int | None] = mapped_column(Integer)
    year_text: Mapped[str | None] = mapped_column(String(60))
    year_on_item: Mapped[str | None] = mapped_column(String(60))

    series: Mapped[str | None] = mapped_column(String(160))
    subject: Mapped[str | None] = mapped_column(Text)

    # Condition.
    grade_scale: Mapped[str | None] = mapped_column(String(24))
    grade_value: Mapped[str | None] = mapped_column(String(40))
    grader: Mapped[str | None] = mapped_column(String(60))
    cert_number: Mapped[str | None] = mapped_column(String(60))
    rarity: Mapped[str | None] = mapped_column(String(40))
    condition_note: Mapped[str | None] = mapped_column(Text)

    # Custody.
    storage: Mapped[str | None] = mapped_column(String(160))
    slot: Mapped[str | None] = mapped_column(String(60))
    barcode: Mapped[str | None] = mapped_column(String(120))

    notes: Mapped[str | None] = mapped_column(Text)
    features: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    completeness: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    coin: Mapped[ItemCoin | None] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )
    banknote: Mapped[ItemBanknote | None] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )
    images: Mapped[list[ItemImage]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ItemImage.sort"
    )
    catalog_refs: Mapped[list[CatalogRef]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    acquisition: Mapped[Acquisition | None] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )
    disposal: Mapped[Disposal | None] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )


class ItemCoin(Base):
    __tablename__ = "item_coin"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), primary_key=True
    )
    diameter_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    shape: Mapped[str | None] = mapped_column(String(60))
    edge_type: Mapped[str | None] = mapped_column(String(80))
    edge_lettering: Mapped[str | None] = mapped_column(Text)
    die_axis: Mapped[str | None] = mapped_column(String(30))
    obv_rev: Mapped[str | None] = mapped_column(String(30))
    composition: Mapped[str | None] = mapped_column(String(160))
    material: Mapped[str | None] = mapped_column(String(80))
    fineness: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    mint: Mapped[str | None] = mapped_column(String(120))
    mintmark: Mapped[str | None] = mapped_column(String(20))
    mintage: Mapped[int | None] = mapped_column(Integer)
    quality: Mapped[str | None] = mapped_column(String(60))

    item: Mapped[Item] = relationship(back_populates="coin")


class ItemBanknote(Base):
    __tablename__ = "item_banknote"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), primary_key=True
    )
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    substrate: Mapped[str | None] = mapped_column(String(40))
    pick_number: Mapped[str | None] = mapped_column(String(40), index=True)
    serial_number: Mapped[str | None] = mapped_column(String(60), index=True)
    serial_prefix: Mapped[str | None] = mapped_column(String(20))
    serial_suffix: Mapped[str | None] = mapped_column(String(20))
    block: Mapped[str | None] = mapped_column(String(20))
    plate: Mapped[str | None] = mapped_column(String(20))
    is_replacement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_combination: Mapped[str | None] = mapped_column(String(120))
    signatories: Mapped[str | None] = mapped_column(Text)
    printer: Mapped[str | None] = mapped_column(String(120))
    watermark: Mapped[str | None] = mapped_column(String(200))
    security_thread: Mapped[str | None] = mapped_column(String(200))
    overprint: Mapped[str | None] = mapped_column(String(200))
    series_year: Mapped[str | None] = mapped_column(String(40))

    item: Mapped[Item] = relationship(back_populates="banknote")


class CatalogRef(Base):
    __tablename__ = "catalog_ref"
    __table_args__ = (UniqueConstraint("item_id", "catalog", "number", name="uq_catalog_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog: Mapped[str] = mapped_column(String(40), nullable=False)
    number: Mapped[str] = mapped_column(String(60), nullable=False)

    item: Mapped[Item] = relationship(back_populates="catalog_refs")


class Acquisition(Base):
    __tablename__ = "acquisition"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date | None] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    counterparty: Mapped[str | None] = mapped_column(String(160))
    place: Mapped[str | None] = mapped_column(String(160))
    invoice_url: Mapped[str | None] = mapped_column(Text)
    info: Mapped[str | None] = mapped_column(Text)

    item: Mapped[Item] = relationship(back_populates="acquisition")


class Disposal(Base):
    __tablename__ = "disposal"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date | None] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    counterparty: Mapped[str | None] = mapped_column(String(160))
    place: Mapped[str | None] = mapped_column(String(160))
    invoice_url: Mapped[str | None] = mapped_column(Text)
    info: Mapped[str | None] = mapped_column(Text)

    item: Mapped[Item] = relationship(back_populates="disposal")


class ItemImage(Base):
    __tablename__ = "item_image"
    __table_args__ = (
        CheckConstraint(f"status IN {IMAGE_STATUSES}", name="ck_image_status"),
        Index("ix_image_item_sort", "item_id", "sort"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID, primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID, ForeignKey("item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    display_path: Mapped[str | None] = mapped_column(Text)
    preview_path: Mapped[str | None] = mapped_column(Text)
    thumb_path: Mapped[str | None] = mapped_column(Text)

    mime: Mapped[str | None] = mapped_column(String(60))
    bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    phash: Mapped[str | None] = mapped_column(String(32), index=True)

    # Crop and enhancement parameters, kept so any derivative can be regenerated from the original.
    transform: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    detection: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    item: Mapped[Item] = relationship(back_populates="images")


class Job(Base):
    """Minimal DB-backed queue so the stack needs no Redis or broker."""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="ck_job_status"),
        Index("ix_job_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    __tablename__ = "login_attempt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
