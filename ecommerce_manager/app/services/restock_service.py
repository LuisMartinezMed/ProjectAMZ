from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import ceil, floor
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AppSetting, Listing, PurchaseOrder, PurchaseOrderLine, Sale, SaleLine
from ..utils.money import q4
from .costs_service import CostsService
from .inventory_service import InventoryService


@dataclass(frozen=True)
class RestockRecommendation:
    listing_id: int
    sku: str
    current_physical_stock: int
    equivalent_listing_stock: int
    stock_on_order: int
    average_daily_listing_sales: Decimal
    average_daily_physical_consumption: Decimal
    days_of_coverage: Optional[Decimal]
    estimated_stockout_date: Optional[date]
    total_replenishment_days: int
    reorder_point_physical_units: int
    suggested_reorder_date: Optional[date]
    target_stock_physical_units: int
    recommended_order_physical_units: int
    recommended_order_supplier_lots: int
    recommended_order_listing_packages: int
    urgency_status: str


class RestockService:
    def __init__(self, session: Session):
        self.session = session
        self.inventory = InventoryService(session)
        self.costs = CostsService(session)

    def recommendation_for_listing(
        self,
        listing_id: int,
        *,
        as_of_date: date,
        velocity_days: Optional[int] = None,
        supplier_lead_time_days: Optional[int] = None,
        shipping_days: Optional[int] = None,
        safety_stock_days: Optional[int] = None,
        target_stock_days: Optional[int] = None,
    ) -> RestockRecommendation:
        listing = self.session.get(Listing, listing_id)
        if listing is None:
            raise ValueError(f"Listing not found: {listing_id}")
        days = velocity_days or self._setting_int("default_sales_velocity_days", 30)
        start_date = as_of_date - timedelta(days=days - 1)
        sold_listing_qty, sold_physical_qty = self._sales_velocity(listing.id, start_date, as_of_date)
        avg_listing = q4(Decimal(sold_listing_qty) / Decimal(days))
        avg_physical = q4(Decimal(sold_physical_qty) / Decimal(days))

        current_stock = self.inventory.current_stock(listing.base_product_id)
        equivalent_listing_stock = floor(current_stock / listing.units_per_listing)
        stock_on_order = self._stock_on_order(listing.base_product_id)
        lead_days = supplier_lead_time_days or self._supplier_or_setting(listing, "default_lead_time_days", 7)
        ship_days = shipping_days or self._supplier_or_setting(listing, "default_shipping_days", 7)
        safety_days = safety_stock_days or self._setting_int("default_safety_stock_days", 14)
        target_days = target_stock_days or self._setting_int("default_target_stock_days", 45)
        replenishment_days = lead_days + ship_days + safety_days

        if avg_physical == 0:
            days_of_coverage = None
            stockout_date = None
            reorder_date = None
            urgency = "healthy"
        else:
            days_of_coverage = q4(Decimal(current_stock) / avg_physical)
            stockout_date = as_of_date + timedelta(days=int(days_of_coverage))
            reorder_date = stockout_date - timedelta(days=replenishment_days)
            if current_stock <= avg_physical * replenishment_days:
                urgency = "urgent"
            elif current_stock <= avg_physical * (replenishment_days + 14):
                urgency = "soon"
            else:
                urgency = "healthy"

        reorder_point = ceil(avg_physical * replenishment_days)
        target_stock = ceil(avg_physical * target_days)
        needed_units = max(0, target_stock - current_stock - stock_on_order)
        supplier_lot_units = self._supplier_lot_units(listing.base_product_id, as_of_date)
        recommended_lots = ceil(needed_units / supplier_lot_units) if needed_units else 0
        recommended_units = recommended_lots * supplier_lot_units
        recommended_listing_packages = floor(recommended_units / listing.units_per_listing)
        if recommended_units == 0 and current_stock > target_stock * 2 and avg_physical > 0:
            urgency = "overstock"

        return RestockRecommendation(
            listing_id=listing.id,
            sku=listing.sku,
            current_physical_stock=current_stock,
            equivalent_listing_stock=equivalent_listing_stock,
            stock_on_order=stock_on_order,
            average_daily_listing_sales=avg_listing,
            average_daily_physical_consumption=avg_physical,
            days_of_coverage=days_of_coverage,
            estimated_stockout_date=stockout_date,
            total_replenishment_days=replenishment_days,
            reorder_point_physical_units=reorder_point,
            suggested_reorder_date=reorder_date,
            target_stock_physical_units=target_stock,
            recommended_order_physical_units=recommended_units,
            recommended_order_supplier_lots=recommended_lots,
            recommended_order_listing_packages=recommended_listing_packages,
            urgency_status=urgency,
        )

    def _sales_velocity(self, listing_id: int, start_date: date, end_date: date) -> tuple[int, int]:
        row = self.session.execute(
            select(
                func.coalesce(func.sum(SaleLine.quantity_listings_sold), 0),
                func.coalesce(func.sum(SaleLine.physical_units_consumed_snapshot), 0),
            )
            .join(Sale, Sale.id == SaleLine.sale_id)
            .where(SaleLine.listing_id == listing_id, Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    def _stock_on_order(self, base_product_id: int) -> int:
        row = self.session.scalar(
            select(
                func.coalesce(
                    func.sum(PurchaseOrderLine.ordered_physical_units - PurchaseOrderLine.received_physical_units),
                    0,
                )
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .where(
                PurchaseOrderLine.base_product_id == base_product_id,
                PurchaseOrder.status.in_(("ordered", "in_transit", "partially_received")),
            )
        )
        return int(row or 0)

    def _supplier_lot_units(self, base_product_id: int, as_of_date: date) -> int:
        try:
            version = self.costs.get_product_cost_version(base_product_id, as_of_date)
            return max(1, version.supplier_lot_units)
        except Exception:
            return 1

    def _supplier_or_setting(self, listing: Listing, attr_name: str, default: int) -> int:
        supplier = listing.base_product.supplier
        value = getattr(supplier, attr_name, None) if supplier else None
        return int(value or self._setting_int(attr_name, default))

    def _setting_int(self, key: str, default: int) -> int:
        setting = self.session.scalar(select(AppSetting).where(AppSetting.key == key))
        if setting is None:
            return default
        try:
            return int(setting.value)
        except (TypeError, ValueError):
            return default

