from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


Money = Numeric(14, 4)
Rate = Numeric(12, 6)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Marketplace(Base):
    __tablename__ = "marketplaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    listings: Mapped[list["Listing"]] = relationship(back_populates="marketplace")


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(200))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    default_lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    default_shipping_days: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    products: Mapped[list["BaseProduct"]] = relationship(back_populates="supplier")


class BaseProduct(TimestampMixin, Base):
    __tablename__ = "base_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(200))
    category: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    upc: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"))
    supplier_product_url: Mapped[Optional[str]] = mapped_column(String(1000))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    supplier: Mapped[Optional[Supplier]] = relationship(back_populates="products")
    listings: Mapped[list["Listing"]] = relationship(back_populates="base_product")
    cost_versions: Mapped[list["ProductCostVersion"]] = relationship(back_populates="base_product")
    inventory_batches: Mapped[list["InventoryBatch"]] = relationship(back_populates="base_product")


class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("marketplace_id", "sku", name="uq_listing_marketplace_sku"),
        CheckConstraint("units_per_listing > 0", name="ck_listing_units_per_listing_positive"),
        Index("ix_listing_marketplace_asin", "marketplace_id", "asin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), nullable=False)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    asin: Mapped[Optional[str]] = mapped_column(String(30))
    listing_name: Mapped[str] = mapped_column(String(500), nullable=False)
    units_per_listing: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amazon_product_url: Mapped[Optional[str]] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    marketplace: Mapped[Marketplace] = relationship(back_populates="listings")
    base_product: Mapped[BaseProduct] = relationship(back_populates="listings")
    listing_cost_versions: Mapped[list["ListingCostVersion"]] = relationship(back_populates="listing")
    fee_versions: Mapped[list["MarketplaceFeeVersion"]] = relationship(back_populates="listing")
    price_versions: Mapped[list["PriceVersion"]] = relationship(back_populates="listing")


class ProductCostVersion(Base):
    __tablename__ = "product_cost_versions"
    __table_args__ = (
        Index("ix_product_cost_effective", "base_product_id", "effective_from", "effective_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    supplier_lot_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    supplier_lot_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supplier_unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    inbound_shipping_cost_per_unit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    warehouse_cost_per_unit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    prep_cost_per_unit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    other_cost_per_unit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total_landed_cost_per_unit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    base_product: Mapped[BaseProduct] = relationship(back_populates="cost_versions")
    supplier: Mapped[Optional[Supplier]] = relationship()


class ListingCostVersion(Base):
    __tablename__ = "listing_cost_versions"
    __table_args__ = (
        Index("ix_listing_cost_effective", "listing_id", "effective_from", "effective_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    warehouse_cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    prep_cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    inbound_shipping_cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    other_cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total_landed_cost_per_listing: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="listing_cost_versions")


class MarketplaceFeeVersion(Base):
    __tablename__ = "marketplace_fee_versions"
    __table_args__ = (
        Index("ix_marketplace_fee_effective", "listing_id", "marketplace_id", "effective_from", "effective_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    referral_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    fba_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    storage_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    amazon_shipping_or_fulfillment_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    other_marketplace_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    estimated_total_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    fee_percentage: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="fee_versions")
    marketplace: Mapped[Marketplace] = relationship()


class PriceVersion(Base):
    __tablename__ = "price_versions"
    __table_args__ = (
        Index("ix_price_effective", "listing_id", "marketplace_id", "effective_from", "effective_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    suggested_selling_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    buybox_percentage: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="price_versions")
    marketplace: Mapped[Marketplace] = relationship()


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_arrival_date: Mapped[Optional[date]] = mapped_column(Date)
    received_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    shipping_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    other_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    ordered_physical_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplier_lot_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    supplier_lot_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supplier_unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    inbound_shipping_allocated: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    received_physical_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    base_product: Mapped[BaseProduct] = relationship()


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"
    __table_args__ = (
        Index("ix_inventory_batch_fifo", "base_product_id", "received_date", "id"),
        CheckConstraint("initial_physical_units >= 0", name="ck_inventory_batch_initial_non_negative"),
        CheckConstraint("remaining_physical_units >= 0", name="ck_inventory_batch_remaining_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    purchase_order_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_order_lines.id"))
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_physical_units: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_physical_units: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_landed_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="available", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    base_product: Mapped[BaseProduct] = relationship(back_populates="inventory_batches")
    purchase_order_line: Mapped[Optional[PurchaseOrderLine]] = relationship()


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_inventory_movement_product_date", "base_product_id", "movement_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    inventory_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory_batches.id"))
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    physical_quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(80))
    reference_id: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    base_product: Mapped[BaseProduct] = relationship()
    inventory_batch: Mapped[Optional[InventoryBatch]] = relationship()


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_date_marketplace", "sale_date", "marketplace_id"),
        Index("ix_sales_order", "order_id"),
        Index("ix_sales_settlement", "settlement_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(String(120))
    settlement_id: Mapped[Optional[str]] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    marketplace: Mapped[Marketplace] = relationship()
    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", cascade="all, delete-orphan")


class SaleLine(Base):
    __tablename__ = "sale_lines"
    __table_args__ = (
        CheckConstraint("quantity_listings_sold > 0", name="ck_sale_line_quantity_positive"),
        Index("ix_sale_line_listing", "listing_id"),
        Index("ix_sale_line_snapshots_sku", "sku_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False)
    base_product_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    asin_snapshot: Mapped[Optional[str]] = mapped_column(String(30))
    listing_name_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    base_product_name_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    units_per_listing_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_listings_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_units_consumed_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_revenue: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    net_received: Mapped[Optional[Decimal]] = mapped_column(Money)
    net_received_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selling_price_per_listing_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    marketplace_fee_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    amazon_shipping_fee_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    referral_fee_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    fba_fee_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    storage_fee_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    supplier_unit_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    supplier_cost_per_listing_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    warehouse_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    inbound_shipping_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    prep_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    other_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total_landed_cost_per_listing_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total_cogs_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    profit_snapshot: Mapped[Optional[Decimal]] = mapped_column(Money)
    margin_snapshot: Mapped[Optional[Decimal]] = mapped_column(Rate)
    roi_snapshot: Mapped[Optional[Decimal]] = mapped_column(Rate)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_reason: Mapped[Optional[str]] = mapped_column(Text)
    cost_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_cost_versions.id"))
    listing_cost_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("listing_cost_versions.id"))
    fee_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("marketplace_fee_versions.id"))
    price_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("price_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="lines")
    listing: Mapped[Listing] = relationship()
    inventory_allocations: Mapped[list["SaleLineInventoryAllocation"]] = relationship(
        back_populates="sale_line", cascade="all, delete-orphan"
    )


class SaleLineInventoryAllocation(Base):
    __tablename__ = "sale_line_inventory_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_line_id: Mapped[int] = mapped_column(ForeignKey("sale_lines.id"), nullable=False)
    inventory_batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id"), nullable=False)
    physical_units_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_cost_snapshot: Mapped[Decimal] = mapped_column(Money, nullable=False)

    sale_line: Mapped[SaleLine] = relationship(back_populates="inventory_allocations")
    inventory_batch: Mapped[InventoryBatch] = relationship()


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("base_products.id"), nullable=False)
    adjustment_date: Mapped[date] = mapped_column(Date, nullable=False)
    physical_quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    base_product: Mapped[BaseProduct] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
