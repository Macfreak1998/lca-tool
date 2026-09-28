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
    nodes: Mapped[list["ChainNode"]] = relationship(
        back_populates="chain", cascade="all, delete-orphan", passive_deletes=True
    )
    edges: Mapped[list["ChainEdge"]] = relationship(
        back_populates="chain", cascade="all, delete-orphan", passive_deletes=True
    )
    combinations: Mapped[list["ChainCombination"]] = relationship(
        back_populates="chain", cascade="all, delete-orphan", passive_deletes=True
    )
    dataset_shares: Mapped[list["ChainDatasetShare"]] = relationship(
        back_populates="chain", cascade="all, delete-orphan", passive_deletes=True
    )
    configurations: Mapped[list["Configuration"]] = relationship(back_populates="chain")


class ChainNode(Base):
    __tablename__ = "chain_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="")
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_functional: Mapped[bool] = mapped_column(Boolean, default=False)
    datasets_differ: Mapped[bool] = mapped_column(Boolean, default=False)

    chain: Mapped[Chain] = relationship(back_populates="nodes")
    role: Mapped[Role | None] = relationship()
    dataset: Mapped[Dataset | None] = relationship()


class ChainEdge(Base):
    __tablename__ = "chain_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))
    target_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32), default="material")
    input_amount: Mapped[float] = mapped_column(Float, default=1.0)
    efficiency: Mapped[float] = mapped_column(Float, default=1.0)
    allocation_share: Mapped[float | None] = mapped_column(Float, nullable=True)

    chain: Mapped[Chain] = relationship(back_populates="edges")
    source: Mapped[ChainNode] = relationship(foreign_keys=[source_id])
    target: Mapped[ChainNode] = relationship(foreign_keys=[target_id])


class ChainCombination(Base):
    __tablename__ = "chain_combinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id", ondelete="CASCADE"))
    process_node_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))

    chain: Mapped[Chain] = relationship(back_populates="combinations")
    process_node: Mapped[ChainNode] = relationship(foreign_keys=[process_node_id])
    axes: Mapped[list["ChainCombinationAxis"]] = relationship(
        back_populates="combination", cascade="all, delete-orphan", passive_deletes=True
    )
    amounts: Mapped[list["ChainCombinationAmount"]] = relationship(
        back_populates="combination", cascade="all, delete-orphan", passive_deletes=True
    )


class ChainCombinationAxis(Base):
    __tablename__ = "chain_combination_axes"
    __table_args__ = (UniqueConstraint("combination_id", "category_node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    combination_id: Mapped[int] = mapped_column(
        ForeignKey("chain_combinations.id", ondelete="CASCADE")
    )
    category_node_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)

    combination: Mapped[ChainCombination] = relationship(back_populates="axes")
    category_node: Mapped[ChainNode] = relationship()
    dataset: Mapped[Dataset | None] = relationship()


class ChainCombinationAmount(Base):
    __tablename__ = "chain_combination_amounts"
    __table_args__ = (UniqueConstraint("combination_id", "category_node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    combination_id: Mapped[int] = mapped_column(
        ForeignKey("chain_combinations.id", ondelete="CASCADE")
    )
    category_node_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))
    input_amount: Mapped[float] = mapped_column(Float, default=0.0)
    efficiency: Mapped[float] = mapped_column(Float, default=1.0)
    recovery_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("chain_nodes.id", ondelete="SET NULL"), nullable=True
    )

    combination: Mapped[ChainCombination] = relationship(back_populates="amounts")
    category_node: Mapped[ChainNode] = relationship(foreign_keys=[category_node_id])
    recovery_node: Mapped[ChainNode | None] = relationship(foreign_keys=[recovery_node_id])


class ChainDatasetShare(Base):
    __tablename__ = "chain_dataset_shares"
    __table_args__ = (UniqueConstraint("category_node_id", "dataset_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id", ondelete="CASCADE"))
    category_node_id: Mapped[int] = mapped_column(ForeignKey("chain_nodes.id", ondelete="CASCADE"))
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    default_share: Mapped[float] = mapped_column(Float, default=1.0)

    chain: Mapped[Chain] = relationship(back_populates="dataset_shares")
    category_node: Mapped[ChainNode] = relationship()
    dataset: Mapped[Dataset] = relationship()


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
    replaced_nodes: Mapped[list["ConfigurationReplacedNode"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )


class ConfigurationSelection(Base):
    __tablename__ = "configuration_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    node_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))

    configuration: Mapped[Configuration] = relationship(back_populates="selections")
    dataset: Mapped[Dataset] = relationship()


class ConfigurationShare(Base):
    __tablename__ = "configuration_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    category_node_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(Integer)
    percent: Mapped[float] = mapped_column(Float)

    configuration: Mapped[Configuration] = relationship(back_populates="shares")


class ConfigurationOptional(Base):
    __tablename__ = "configuration_optional"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    node_id: Mapped[int] = mapped_column(Integer)

    configuration: Mapped[Configuration] = relationship(back_populates="optional_on")


class ConfigurationReplacedNode(Base):
    __tablename__ = "configuration_replaced_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE")
    )
    node_id: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))

    configuration: Mapped[Configuration] = relationship(back_populates="replaced_nodes")
    dataset: Mapped[Dataset] = relationship()


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
