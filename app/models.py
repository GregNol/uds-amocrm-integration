from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TokenStore(Base):
    """OAuth-токены amoCRM. Храним одну активную запись (id=1)."""

    __tablename__ = "amocrm_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CustomerMap(Base):
    """Связка клиента UDS ↔ контакта amoCRM."""

    __tablename__ = "customer_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    uds_customer_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amocrm_contact_id: Mapped[int] = mapped_column(BigInteger, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DealMap(Base):
    """Связка заказа/покупки UDS ↔ сделки amoCRM."""

    __tablename__ = "deal_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    uds_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amocrm_lead_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open|won
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EventLog(Base):
    """Журнал входящих событий UDS — обеспечивает идемпотентность и аудит."""

    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(191), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    processed: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
