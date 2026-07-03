from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    BaseProduct,
    InventoryBatch,
    InventoryMovement,
    Listing,
    MarketplaceFeeVersion,
    ProductCostVersion,
    Sale,
    SaleLine,
)
from ..utils.money import q4, safe_divide


@dataclass(frozen=True)
class DashboardMetrics:
    total_gross_revenue: Decimal
    total_net_received: Decimal
    total_cogs: Decimal
    total_profit: Decimal
    total_listings_sold: int
    total_physical_units_consumed: int
    margin: Optional[Decimal]
    roi: Optional[Decimal]


@dataclass(frozen=True)
class ListingProfitRow:
    listing_id: int
    sku_snapshot: str
    listing_name_snapshot: str
    listings_sold: int
    gross: Decimal
    net: Decimal
    cogs: Decimal
    profit: Decimal
    margin: Optional[Decimal]
    roi: Optional[Decimal]


@dataclass(frozen=True)
class ProductProfitRow:
    base_product_id: int
    base_product_name: str
    listings_sold: int
    gross: Decimal
    net: Decimal
    cogs: Decimal
    profit: Decimal
    margin: Optional[Decimal]
    roi: Optional[Decimal]


@dataclass(frozen=True)
class DataAuditSummary:
    products: int
    listings: int
    sales: int
    inventory_batches: int
    products_without_cost_version: int
    listings_without_fee_version: int
    sales_with_estimated_net_received: int
    sales_needing_review: int
    listings_with_negative_profit: int
    listings_with_margin_below_5: int
    listings_with_zero_or_low_stock: int
    products_with_stock_discrepancy: int


class ReportsService:
    def __init__(self, session: Session):
        self.session = session

    def dashboard_metrics(
        self,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        marketplace_id: Optional[int] = None,
    ) -> DashboardMetrics:
        stmt = select(
            func.coalesce(func.sum(SaleLine.gross_revenue), 0),
            func.coalesce(func.sum(SaleLine.net_received), 0),
            func.coalesce(func.sum(SaleLine.total_cogs_snapshot), 0),
            func.coalesce(func.sum(SaleLine.profit_snapshot), 0),
            func.coalesce(func.sum(SaleLine.quantity_listings_sold), 0),
            func.coalesce(func.sum(SaleLine.physical_units_consumed_snapshot), 0),
        ).join(Sale, Sale.id == SaleLine.sale_id)
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        if marketplace_id:
            stmt = stmt.where(Sale.marketplace_id == marketplace_id)
        gross, net, cogs, profit, listings, physical = self.session.execute(stmt).one()
        gross = q4(gross)
        cogs = q4(cogs)
        profit = q4(profit)
        return DashboardMetrics(
            total_gross_revenue=gross,
            total_net_received=q4(net),
            total_cogs=cogs,
            total_profit=profit,
            total_listings_sold=int(listings or 0),
            total_physical_units_consumed=int(physical or 0),
            margin=safe_divide(profit, gross),
            roi=safe_divide(profit, cogs),
        )

    def profit_by_listing(
        self, *, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> list[ListingProfitRow]:
        stmt = (
            select(
                SaleLine.listing_id,
                SaleLine.sku_snapshot,
                SaleLine.listing_name_snapshot,
                func.coalesce(func.sum(SaleLine.quantity_listings_sold), 0).label("listings_sold"),
                func.coalesce(func.sum(SaleLine.gross_revenue), 0).label("gross"),
                func.coalesce(func.sum(SaleLine.net_received), 0).label("net"),
                func.coalesce(func.sum(SaleLine.total_cogs_snapshot), 0).label("cogs"),
                func.coalesce(func.sum(SaleLine.profit_snapshot), 0).label("profit"),
            )
            .join(Sale, Sale.id == SaleLine.sale_id)
            .group_by(SaleLine.listing_id, SaleLine.sku_snapshot, SaleLine.listing_name_snapshot)
            .order_by(func.sum(SaleLine.profit_snapshot).desc())
        )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        rows: list[ListingProfitRow] = []
        for row in self.session.execute(stmt).all():
            gross = q4(row.gross)
            cogs = q4(row.cogs)
            profit = q4(row.profit)
            rows.append(
                ListingProfitRow(
                    listing_id=row.listing_id,
                    sku_snapshot=row.sku_snapshot,
                    listing_name_snapshot=row.listing_name_snapshot,
                    listings_sold=int(row.listings_sold or 0),
                    gross=gross,
                    net=q4(row.net),
                    cogs=cogs,
                    profit=profit,
                    margin=safe_divide(profit, gross),
                    roi=safe_divide(profit, cogs),
                )
            )
        return rows

    def profit_by_product(
        self, *, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> list[ProductProfitRow]:
        stmt = (
            select(
                SaleLine.base_product_id_snapshot,
                SaleLine.base_product_name_snapshot,
                func.coalesce(func.sum(SaleLine.quantity_listings_sold), 0).label("listings_sold"),
                func.coalesce(func.sum(SaleLine.gross_revenue), 0).label("gross"),
                func.coalesce(func.sum(SaleLine.net_received), 0).label("net"),
                func.coalesce(func.sum(SaleLine.total_cogs_snapshot), 0).label("cogs"),
                func.coalesce(func.sum(SaleLine.profit_snapshot), 0).label("profit"),
            )
            .join(Sale, Sale.id == SaleLine.sale_id)
            .group_by(SaleLine.base_product_id_snapshot, SaleLine.base_product_name_snapshot)
            .order_by(func.sum(SaleLine.profit_snapshot).desc())
        )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        rows: list[ProductProfitRow] = []
        for row in self.session.execute(stmt).all():
            gross = q4(row.gross)
            cogs = q4(row.cogs)
            profit = q4(row.profit)
            rows.append(
                ProductProfitRow(
                    base_product_id=row.base_product_id_snapshot,
                    base_product_name=row.base_product_name_snapshot,
                    listings_sold=int(row.listings_sold or 0),
                    gross=gross,
                    net=q4(row.net),
                    cogs=cogs,
                    profit=profit,
                    margin=safe_divide(profit, gross),
                    roi=safe_divide(profit, cogs),
                )
            )
        return rows

    def inventory_valuation(self):
        stmt = (
            select(
                InventoryBatch.base_product_id,
                func.coalesce(func.sum(InventoryBatch.remaining_physical_units), 0).label("units"),
                func.coalesce(
                    func.sum(InventoryBatch.remaining_physical_units * InventoryBatch.unit_landed_cost), 0
                ).label("value"),
            )
            .group_by(InventoryBatch.base_product_id)
            .order_by(InventoryBatch.base_product_id)
        )
        return self.session.execute(stmt).all()

    def current_stock_by_listing(self):
        stmt = (
            select(
                Listing.id,
                Listing.sku,
                Listing.listing_name,
                BaseProduct.name.label("base_product_name"),
                Listing.units_per_listing,
                func.coalesce(func.sum(InventoryBatch.remaining_physical_units), 0).label("physical_stock"),
            )
            .join(BaseProduct, BaseProduct.id == Listing.base_product_id)
            .outerjoin(InventoryBatch, InventoryBatch.base_product_id == BaseProduct.id)
            .group_by(
                Listing.id,
                Listing.sku,
                Listing.listing_name,
                BaseProduct.name,
                Listing.units_per_listing,
            )
            .order_by(Listing.sku)
        )
        rows = []
        for row in self.session.execute(stmt).all():
            physical_stock = int(row.physical_stock or 0)
            rows.append(
                {
                    "listing_id": row.id,
                    "sku": row.sku,
                    "listing_name": row.listing_name,
                    "base_product_name": row.base_product_name,
                    "units_per_listing": row.units_per_listing,
                    "physical_stock": physical_stock,
                    "equivalent_listing_stock": physical_stock // row.units_per_listing,
                }
            )
        return rows

    def current_stock_by_product(self):
        stmt = (
            select(
                BaseProduct.id,
                BaseProduct.name,
                func.coalesce(func.sum(InventoryBatch.remaining_physical_units), 0).label("physical_stock"),
            )
            .outerjoin(InventoryBatch, InventoryBatch.base_product_id == BaseProduct.id)
            .group_by(BaseProduct.id, BaseProduct.name)
            .order_by(BaseProduct.name)
        )
        return self.session.execute(stmt).all()

    def fifo_batches(self):
        stmt = (
            select(
                InventoryBatch.id,
                BaseProduct.name.label("base_product_name"),
                InventoryBatch.received_date,
                InventoryBatch.initial_physical_units,
                InventoryBatch.remaining_physical_units,
                InventoryBatch.unit_landed_cost,
                InventoryBatch.status,
                InventoryBatch.warehouse_location,
            )
            .join(BaseProduct, BaseProduct.id == InventoryBatch.base_product_id)
            .order_by(BaseProduct.name, InventoryBatch.received_date, InventoryBatch.id)
        )
        return self.session.execute(stmt).all()

    def inventory_movements(self, limit: int = 200):
        stmt = (
            select(
                InventoryMovement.id,
                BaseProduct.name.label("base_product_name"),
                InventoryMovement.movement_date,
                InventoryMovement.movement_type,
                InventoryMovement.physical_quantity_change,
                InventoryMovement.reference_type,
                InventoryMovement.reference_id,
                InventoryMovement.notes,
            )
            .join(BaseProduct, BaseProduct.id == InventoryMovement.base_product_id)
            .order_by(InventoryMovement.movement_date.desc(), InventoryMovement.id.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).all()

    def recent_sales(self, limit: int = 100):
        stmt = (
            select(
                SaleLine.id,
                Sale.sale_date,
                SaleLine.sku_snapshot,
                SaleLine.listing_name_snapshot,
                SaleLine.quantity_listings_sold,
                SaleLine.physical_units_consumed_snapshot,
                SaleLine.gross_revenue,
                SaleLine.net_received,
                SaleLine.total_cogs_snapshot,
                SaleLine.profit_snapshot,
                SaleLine.margin_snapshot,
                SaleLine.roi_snapshot,
                Sale.source,
            )
            .join(Sale, Sale.id == SaleLine.sale_id)
            .order_by(Sale.sale_date.desc(), SaleLine.id.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).all()

    def data_audit(self) -> DataAuditSummary:
        products = int(self.session.scalar(select(func.count(BaseProduct.id))) or 0)
        listings = int(self.session.scalar(select(func.count(Listing.id))) or 0)
        sales = int(self.session.scalar(select(func.count(SaleLine.id))) or 0)
        batches = int(self.session.scalar(select(func.count(InventoryBatch.id))) or 0)
        products_without_cost = int(
            self.session.scalar(
                select(func.count(BaseProduct.id))
                .outerjoin(ProductCostVersion, ProductCostVersion.base_product_id == BaseProduct.id)
                .where(ProductCostVersion.id.is_(None))
            )
            or 0
        )
        listings_without_fee = int(
            self.session.scalar(
                select(func.count(Listing.id))
                .outerjoin(MarketplaceFeeVersion, MarketplaceFeeVersion.listing_id == Listing.id)
                .where(MarketplaceFeeVersion.id.is_(None))
            )
            or 0
        )
        estimated_net = int(
            self.session.scalar(select(func.count(SaleLine.id)).where(SaleLine.net_received_estimated.is_(True)))
            or 0
        )
        needs_review = int(
            self.session.scalar(select(func.count(SaleLine.id)).where(SaleLine.needs_review.is_(True))) or 0
        )
        profit_rows = self.profit_by_listing()
        negative_profit = sum(1 for row in profit_rows if row.profit < 0)
        low_margin = sum(1 for row in profit_rows if row.margin is not None and row.margin < Decimal("0.05"))
        low_stock = sum(1 for row in self.current_stock_by_listing() if row["equivalent_listing_stock"] <= 5)
        stock_discrepancy = self._stock_discrepancy_count()
        return DataAuditSummary(
            products=products,
            listings=listings,
            sales=sales,
            inventory_batches=batches,
            products_without_cost_version=products_without_cost,
            listings_without_fee_version=listings_without_fee,
            sales_with_estimated_net_received=estimated_net,
            sales_needing_review=needs_review,
            listings_with_negative_profit=negative_profit,
            listings_with_margin_below_5=low_margin,
            listings_with_zero_or_low_stock=low_stock,
            products_with_stock_discrepancy=stock_discrepancy,
        )

    def _stock_discrepancy_count(self) -> int:
        batch_rows = {
            row.base_product_id: int(row.stock or 0)
            for row in self.session.execute(
                select(
                    InventoryBatch.base_product_id,
                    func.coalesce(func.sum(InventoryBatch.remaining_physical_units), 0).label("stock"),
                ).group_by(InventoryBatch.base_product_id)
            ).all()
        }
        movement_rows = {
            row.base_product_id: int(row.stock or 0)
            for row in self.session.execute(
                select(
                    InventoryMovement.base_product_id,
                    func.coalesce(func.sum(InventoryMovement.physical_quantity_change), 0).label("stock"),
                ).group_by(InventoryMovement.base_product_id)
            ).all()
        }
        product_ids = set(batch_rows) | set(movement_rows)
        return sum(1 for product_id in product_ids if batch_rows.get(product_id, 0) != movement_rows.get(product_id, 0))
