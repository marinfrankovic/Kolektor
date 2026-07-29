from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Kind = Literal["coin", "banknote", "token", "set", "other"]
Status = Literal["owned", "wish", "ordered", "duplicate", "for_sale", "sold", "missing"]
ImageRole = Literal[
    "obverse", "reverse", "face", "back", "edge", "watermark", "detail", "certificate", "other"
]
Language = Literal["en", "hr"]
AuthMode = Literal["password", "open"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SetupStatus(BaseModel):
    setup_required: bool
    auth_mode: AuthMode
    languages: list[Language] = ["en", "hr"]
    default_language: Language = "en"


class SetupRequest(BaseModel):
    auth_mode: AuthMode
    language: Language = "en"
    email: EmailStr | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _password_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 10:
            raise ValueError("password must be at least 10 characters")
        return v


class AuthModeChange(BaseModel):
    auth_mode: AuthMode
    email: EmailStr | None = None
    password: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class UserOut(ORMModel):
    id: uuid.UUID
    # Plain str: open mode stores a placeholder address that no real mailbox backs.
    email: str
    display_name: str | None = None
    language: Language = "en"
    must_change_password: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    language: Language | None = None


# --- sub-resources ----------------------------------------------------------


class CoinIn(BaseModel):
    diameter_mm: Decimal | None = None
    weight_g: Decimal | None = None
    thickness_mm: Decimal | None = None
    shape: str | None = None
    edge_type: str | None = None
    edge_lettering: str | None = None
    die_axis: str | None = None
    obv_rev: str | None = None
    composition: str | None = None
    material: str | None = None
    fineness: Decimal | None = None
    mint: str | None = None
    mintmark: str | None = None
    mintage: int | None = None
    quality: str | None = None


class CoinOut(CoinIn, ORMModel):
    pass


class BanknoteIn(BaseModel):
    width_mm: Decimal | None = None
    height_mm: Decimal | None = None
    substrate: str | None = None
    pick_number: str | None = None
    serial_number: str | None = None
    serial_prefix: str | None = None
    serial_suffix: str | None = None
    block: str | None = None
    plate: str | None = None
    is_replacement: bool = False
    signature_combination: str | None = None
    signatories: str | None = None
    printer: str | None = None
    watermark: str | None = None
    security_thread: str | None = None
    overprint: str | None = None
    series_year: str | None = None


class BanknoteOut(BanknoteIn, ORMModel):
    pass


class MoneyEventIn(BaseModel):
    date: date_type | None = None
    price: Decimal | None = None
    commission: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    counterparty: str | None = None
    place: str | None = None
    invoice_url: str | None = None
    info: str | None = None


class MoneyEventOut(MoneyEventIn, ORMModel):
    pass


class CatalogRefIn(BaseModel):
    catalog: str = Field(max_length=40)
    number: str = Field(max_length=60)


class CatalogRefOut(CatalogRefIn, ORMModel):
    id: int


class ImageOut(ORMModel):
    id: uuid.UUID
    role: ImageRole
    sort: int
    status: str
    width: int | None = None
    height: int | None = None
    phash: str | None = None
    transform: dict[str, Any] = {}
    detection: dict[str, Any] = {}
    error: str | None = None
    created_at: datetime


class ImageImport(BaseModel):
    item_id: uuid.UUID
    role: ImageRole = "other"
    url: str = Field(min_length=8, max_length=2000)


# --- items ------------------------------------------------------------------


class ItemBase(BaseModel):
    kind: Kind = "coin"
    title: str | None = Field(default=None, max_length=300)
    status: Status = "owned"
    quantity: int = Field(default=1, ge=0)

    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    map_country_code: str | None = Field(default=None, min_length=2, max_length=2)
    issuing_entity: str | None = None
    region: str | None = None
    period: str | None = None
    ruler: str | None = None

    denomination_value: Decimal | None = None
    denomination_text: str | None = None
    currency_unit: str | None = None

    year: int | None = None
    year_text: str | None = None
    year_on_item: str | None = None

    series: str | None = None
    subject: str | None = None

    grade_scale: str | None = None
    grade_value: str | None = None
    grader: str | None = None
    cert_number: str | None = None
    rarity: str | None = None
    condition_note: str | None = None

    storage: str | None = None
    slot: str | None = None
    barcode: str | None = None

    notes: str | None = None
    features: str | None = None
    tags: list[str] = []
    extra: dict[str, Any] = {}

    @field_validator("country_code", "map_country_code")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ItemCreate(ItemBase):
    coin: CoinIn | None = None
    banknote: BanknoteIn | None = None
    acquisition: MoneyEventIn | None = None
    disposal: MoneyEventIn | None = None
    catalog_refs: list[CatalogRefIn] = []


class ItemUpdate(ItemCreate):
    kind: Kind | None = None
    status: Status | None = None
    quantity: int | None = Field(default=None, ge=0)


class ItemOut(ItemBase, ORMModel):
    id: uuid.UUID
    title: str
    completeness: int
    created_at: datetime
    updated_at: datetime
    coin: CoinOut | None = None
    banknote: BanknoteOut | None = None
    acquisition: MoneyEventOut | None = None
    disposal: MoneyEventOut | None = None
    catalog_refs: list[CatalogRefOut] = []
    images: list[ImageOut] = []


class ItemListRow(ORMModel):
    id: uuid.UUID
    kind: Kind
    title: str
    status: Status
    quantity: int
    country_code: str | None = None
    map_country_code: str | None = None
    issuing_entity: str | None = None
    denomination_text: str | None = None
    denomination_value: Decimal | None = None
    currency_unit: str | None = None
    year: int | None = None
    grade_value: str | None = None
    completeness: int
    thumb_image_id: uuid.UUID | None = None
    updated_at: datetime


class ItemPage(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[ItemListRow]


# --- reference and stats ----------------------------------------------------


class CountryOut(ORMModel):
    code2: str
    code3: str
    numeric3: str
    name: str
    continent: str | None = None


class HistoricalEntityOut(ORMModel):
    id: int
    name: str
    successor_code2: str | None = None
    from_year: int | None = None
    to_year: int | None = None
    note: str | None = None


class MapCountryStat(BaseModel):
    code2: str
    numeric3: str
    name: str
    continent: str | None = None
    coins: int = 0
    banknotes: int = 0
    other: int = 0
    total: int = 0


class MapStats(BaseModel):
    countries: list[MapCountryStat]
    covered: int
    sovereign_total: int
    by_continent: dict[str, int]


class CollectionStats(BaseModel):
    items: int
    pieces: int
    coins: int
    banknotes: int
    countries: int
    images: int
    year_min: int | None = None
    year_max: int | None = None
    spend_by_currency: dict[str, Decimal]
    average_completeness: float
