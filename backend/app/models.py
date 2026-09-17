from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="owner")
    configurations: Mapped[list["Configuration"]] = relationship(back_populates="user")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200))


class EndProduct(Base):
    __tablename__ = "end_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(32))

    chains: Mapped[list["Chain"]] = relationship(back_populates="end_product")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(64), default="")
    unit: Mapped[str] = mapped_column(String(32))
    source_kind: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(255), default="")
    activity_name: Mapped[str] = mapped_column(String(500), default="")
    product_uuid: Mapped[str] = mapped_column(String(64), default="")
    activity_uuid: Mapped[str] = mapped_column(String(64), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    inputs_doc: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped[User | None] = relationship(back_populates="datasets")
    roles: Mapped[list["DatasetRole"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    factors: Mapped[list["DatasetFactor"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    exchanges: Mapped[list["DatasetExchange"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetRole(Base):
    __tablename__ = "dataset_roles"
    __table_args__ = (UniqueConstraint("dataset_id", "role_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))

    dataset: Mapped[Dataset] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class DatasetFactor(Base):
    __tablename__ = "dataset_factors"
    __table_args__ = (UniqueConstraint("dataset_id", "method_id", "indicator_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    method_id: Mapped[str] = mapped_column(String(32), default="EF3.1")
    indicator_id: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="factors")


class DatasetExchange(Base):
    __tablename__ = "dataset_exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    flow_id: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(500), default="")
    compartment: Mapped[str] = mapped_column(String(120), default="")
    subcompartment: Mapped[str] = mapped_column(String(200), default="")
    unit: Mapped[str] = mapped_column(String(32), default="kg")
    amount: Mapped[float] = mapped_column(Float)

    dataset: Mapped[Dataset] = relationship(back_populates="exchanges")


class DatasetProposal(Base):
    __tablename__ = "dataset_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="open")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user_dataset: Mapped[Dataset] = relationship()


class Chain(Base):
    __tablename__ = "chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    end_product_id: Mapped[int] = mapped_column(ForeignKey("end_products.id"))
    end_unit: Mapped[str] = mapped_column(String(32))

    end_product: Mapped[EndProduct] = relationship(back_populates="chains")
    stages: Mapped[list["Stage"]] = relationship(
        back_populates="chain", cascade="all, delete-orphan", order_by="Stage.sort_order"
    )
    configurations: Mapped[list["Configuration"]] = relationship(back_populates="chain")


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    outgoing_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id"), nullable=True
    )
    upstream_amount: Mapped[float] = mapped_column(Float, default=1.0)

    chain: Mapped[Chain] = relationship(back_populates="stages")
    slots: Mapped[list["Slot"]] = relationship(
        back_populates="stage", cascade="all, delete-orphan"
    )


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    optional_default_off: Mapped[bool] = mapped_column(Boolean, default=False)
    min_count: Mapped[int] = mapped_column(Integer, default=1)
    specific_amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    default_dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets.id"), nullable=True
    )
    default_share: Mapped[float] = mapped_column(Float, default=1.0)

    stage: Mapped[Stage] = relationship(back_populates="slots")
    role: Mapped[Role] = relationship()
    default_dataset: Mapped[Dataset | None] = relationship()


class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id"))
    name: Mapped[str] = mapped_column(String(200), default="Konfiguration")
    end_amount: Mapped[float] = mapped_column(Float)
    invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="configurations")
    chain: Mapped[Chain] = relationship(back_populates="configurations")
    selections: Mapped[list["ConfigurationSelection"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    shares: Mapped[list["ConfigurationShare"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    optional_on: Mapped[list["ConfigurationOptional"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    extra_slots: Mapped[list["ConfigurationExtraSlot"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    replaced_stages: Mapped[list["ConfigurationReplacedStage"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )


class ConfigurationSelection(Base):
    __tablename__ = "configuration_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    slot_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))

    configuration: Mapped[Configuration] = relationship(back_populates="selections")
    dataset: Mapped[Dataset] = relationship()


class ConfigurationShare(Base):
    __tablename__ = "configuration_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    slot_key: Mapped[str] = mapped_column(String(64))
    percent: Mapped[float] = mapped_column(Float)

    configuration: Mapped[Configuration] = relationship(back_populates="shares")


class ConfigurationOptional(Base):
    __tablename__ = "configuration_optional"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    slot_id: Mapped[int] = mapped_column(Integer)

    configuration: Mapped[Configuration] = relationship(back_populates="optional_on")


class ConfigurationExtraSlot(Base):
    __tablename__ = "configuration_extra_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    stage_id: Mapped[int] = mapped_column(Integer)
    role_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    share: Mapped[float] = mapped_column(Float, default=0.0)

    configuration: Mapped[Configuration] = relationship(back_populates="extra_slots")
    dataset: Mapped[Dataset] = relationship()


class ConfigurationReplacedStage(Base):
    __tablename__ = "configuration_replaced_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    stage_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))

    configuration: Mapped[Configuration] = relationship(back_populates="replaced_stages")
    dataset: Mapped[Dataset] = relationship()


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
