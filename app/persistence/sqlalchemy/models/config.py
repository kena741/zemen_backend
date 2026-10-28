from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base


class Banner(Base):
    __tablename__ = "banner"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    banner_name: Mapped[str | None] = mapped_column("bannerName", Text, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CountryTax(Base):
    __tablename__ = "country_tax"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fix: Mapped[bool | None] = mapped_column("isFix", Boolean, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)


class Coupon(Base):
    __tablename__ = "coupon"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column("expiredAt", DateTime(timezone=True), nullable=True)
    is_private: Mapped[bool | None] = mapped_column("isPrivate", Boolean, nullable=True)
    is_fix: Mapped[bool | None] = mapped_column("isFix", Boolean, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_amount: Mapped[Decimal | None] = mapped_column("minAmount", Numeric, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MobileAppConfig(Base):
    __tablename__ = "mobile_app_config"

    app_key: Mapped[str] = mapped_column(Text, primary_key=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maintenance_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenance_affected_versions: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    update_needed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    update_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_affected_versions: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column("createdAt", DateTime(timezone=True), nullable=True)
    decimal_digits: Mapped[str | None] = mapped_column("decimalDigits", Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol_at_right: Mapped[bool | None] = mapped_column("symbolAtRight", Boolean, nullable=True)


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
