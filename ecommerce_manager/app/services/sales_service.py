from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Sale, SaleLine, SaleLineInventoryAllocation
from ..utils.money import q4, safe_divide
from ..utils.validators import (
    ValidationError,
    require_non_negative_decimal,
    require_positive_int,
)
from .costs_service import CostsService
from .inventory_service import InventoryService
from .products_service import ProductsService


@dataclass(frozen=True)
class SaleLineInput:
    sale_date: date
    sku: Optional[str]
    asin: Optional[str]
    quantity_listings_sold: int
    gross_revenue: Decimal
    net_received: Optional[Decimal] = None
    order_id: Optional[str] = None
    settlement_id: Optional[str] = None
    source: str = "manual"
    notes: Optional[str] = None


@dataclass(frozen=True)
class SalePreview:
    listing_id: int
    sku: str
    listing_name: str
    base_product_name: str
    units_per_listing: int
    quantity_listings_sold: int
    physical_units_consumed: int
    total_cogs: Decimal
    net_received: Decimal
    net_received_estimated: bool
    profit: Decimal
    margin: Optional[Decimal]
    roi: Optional[Decimal]
    allocation_summary: str


class SalesService:
    def __init__(self, session: Session):
        self.session = session
        self.products = ProductsService(session)
        self.costs = CostsService(session)
        self.inventory = InventoryService(session)

    def add_manual_sale(
        self,
        *,
        sale_date: date,
        sku: Optional[str] = None,
        asin: Optional[str] = None,
        quantity_listings_sold: int,
        gross_revenue: Decimal | int | str,
        net_received: Decimal | int | str | None,
        order_id: Optional[str] = None,
        settlement_id: Optional[str] = None,
        notes: Optional[str] = None,
        source: str = "manual",
    ) -> SaleLine:
        sale_input = SaleLineInput(
            sale_date=sale_date,
            sku=sku,
            asin=asin,
            quantity_listings_sold=quantity_listings_sold,
            gross_revenue=require_non_negative_decimal(gross_revenue, "Gross revenue"),
            net_received=None if net_received is None else require_non_negative_decimal(net_received, "Net received"),
            order_id=order_id,
            settlement_id=settlement_id,
            source=source,
            notes=notes,
        )
        return self.add_sale_line(sale_input)

    def add_bulk_sales(self, rows: list[SaleLineInput]) -> list[SaleLine]:
        return [self.add_sale_line(row) for row in rows]

    def preview_sale_line(self, sale_input: SaleLineInput) -> SalePreview:
        quantity = require_positive_int(sale_input.quantity_listings_sold, "Quantity sold")
        gross_revenue = require_non_negative_decimal(sale_input.gross_revenue, "Gross revenue")
        listing = self.products.find_listing(sku=sale_input.sku, asin=sale_input.asin)
        base_product = listing.base_product
        physical_units = quantity * listing.units_per_listing
        product_cost = self.costs.get_product_cost_version(base_product.id, sale_input.sale_date)
        fee_version = self.costs.get_marketplace_fee_version(
            listing.id, listing.marketplace_id, sale_input.sale_date
        )
        allocations = self.inventory.preview_fifo_allocation(
            base_product_id=base_product.id,
            physical_units=physical_units,
        )
        total_cogs = q4(sum((allocation.total_cost for allocation in allocations), Decimal("0")))
        marketplace_fee_total = q4((fee_version.estimated_total_fee if fee_version else Decimal("0")) * quantity)
        net_received_estimated = False
        if sale_input.net_received is None:
            if fee_version is None:
                raise ValidationError("Net received is required when no fee version is available")
            net_received = q4(gross_revenue - marketplace_fee_total)
            net_received_estimated = True
        else:
            net_received = q4(sale_input.net_received)
        profit = q4(net_received - total_cogs)
        allocation_summary = ", ".join(
            f"batch {allocation.batch_id}: {allocation.physical_units} @ {allocation.unit_cost}"
            for allocation in allocations
        )
        return SalePreview(
            listing_id=listing.id,
            sku=listing.sku,
            listing_name=listing.listing_name,
            base_product_name=base_product.name,
            units_per_listing=listing.units_per_listing,
            quantity_listings_sold=quantity,
            physical_units_consumed=physical_units,
            total_cogs=total_cogs,
            net_received=net_received,
            net_received_estimated=net_received_estimated,
            profit=profit,
            margin=safe_divide(profit, gross_revenue),
            roi=safe_divide(profit, total_cogs),
            allocation_summary=allocation_summary,
        )

    def add_sale_line(self, sale_input: SaleLineInput) -> SaleLine:
        quantity = require_positive_int(sale_input.quantity_listings_sold, "Quantity sold")
        listing = self.products.find_listing(sku=sale_input.sku, asin=sale_input.asin)
        base_product = listing.base_product
        physical_units = quantity * listing.units_per_listing

        product_cost = self.costs.get_product_cost_version(base_product.id, sale_input.sale_date)
        listing_cost = self.costs.get_listing_cost_version(listing.id, sale_input.sale_date)
        fee_version = self.costs.get_marketplace_fee_version(
            listing.id, listing.marketplace_id, sale_input.sale_date
        )
        price_version = self.costs.get_price_version(listing.id, listing.marketplace_id, sale_input.sale_date)

        allocations = self.inventory.allocate_fifo(
            base_product_id=base_product.id,
            physical_units=physical_units,
            movement_date=sale_input.sale_date,
        )
        total_cogs = q4(sum((allocation.total_cost for allocation in allocations), Decimal("0")))

        marketplace_fee_total = q4((fee_version.estimated_total_fee if fee_version else Decimal("0")) * quantity)
        net_received_estimated = False
        if sale_input.net_received is None:
            if fee_version is None:
                raise ValidationError("Net received is required when no fee version is available")
            net_received = q4(sale_input.gross_revenue - marketplace_fee_total)
            net_received_estimated = True
        else:
            net_received = q4(sale_input.net_received)

        profit = q4(net_received - total_cogs)
        margin = safe_divide(profit, sale_input.gross_revenue)
        roi = safe_divide(profit, total_cogs)
        selling_price = q4(sale_input.gross_revenue / quantity)
        weighted_fifo_unit_cost = q4(total_cogs / physical_units)
        fifo_cost_per_listing = q4(weighted_fifo_unit_cost * listing.units_per_listing)
        if listing_cost:
            warehouse_cost = q4(listing_cost.warehouse_cost_per_listing)
            inbound_cost = q4(listing_cost.inbound_shipping_cost_per_listing)
            prep_cost = q4(listing_cost.prep_cost_per_listing)
            other_cost = q4(listing_cost.other_cost_per_listing)
        else:
            warehouse_cost = q4(product_cost.warehouse_cost_per_unit * listing.units_per_listing)
            inbound_cost = q4(product_cost.inbound_shipping_cost_per_unit * listing.units_per_listing)
            prep_cost = q4(product_cost.prep_cost_per_unit * listing.units_per_listing)
            other_cost = q4(product_cost.other_cost_per_unit * listing.units_per_listing)

        sale = Sale(
            sale_date=sale_input.sale_date,
            marketplace_id=listing.marketplace_id,
            order_id=sale_input.order_id,
            settlement_id=sale_input.settlement_id,
            source=sale_input.source,
            notes=sale_input.notes,
        )
        self.session.add(sale)
        self.session.flush()

        sale_line = SaleLine(
            sale_id=sale.id,
            listing_id=listing.id,
            base_product_id_snapshot=base_product.id,
            sku_snapshot=listing.sku,
            asin_snapshot=listing.asin,
            listing_name_snapshot=listing.listing_name,
            base_product_name_snapshot=base_product.name,
            units_per_listing_snapshot=listing.units_per_listing,
            quantity_listings_sold=quantity,
            physical_units_consumed_snapshot=physical_units,
            gross_revenue=q4(sale_input.gross_revenue),
            net_received=net_received,
            net_received_estimated=net_received_estimated,
            selling_price_per_listing_snapshot=selling_price,
            marketplace_fee_snapshot=marketplace_fee_total,
            amazon_shipping_fee_snapshot=q4(
                (fee_version.amazon_shipping_or_fulfillment_fee if fee_version else 0) * quantity
            ),
            referral_fee_snapshot=q4((fee_version.referral_fee if fee_version else 0) * quantity),
            fba_fee_snapshot=q4((fee_version.fba_fee if fee_version else 0) * quantity),
            storage_fee_snapshot=q4((fee_version.storage_fee if fee_version else 0) * quantity),
            supplier_unit_cost_snapshot=weighted_fifo_unit_cost,
            supplier_cost_per_listing_snapshot=fifo_cost_per_listing,
            warehouse_cost_snapshot=warehouse_cost,
            inbound_shipping_cost_snapshot=inbound_cost,
            prep_cost_snapshot=prep_cost,
            other_cost_snapshot=other_cost,
            total_landed_cost_per_listing_snapshot=fifo_cost_per_listing,
            total_cogs_snapshot=total_cogs,
            profit_snapshot=profit,
            margin_snapshot=margin,
            roi_snapshot=roi,
            cost_version_id=product_cost.id,
            listing_cost_version_id=listing_cost.id if listing_cost else None,
            fee_version_id=fee_version.id if fee_version else None,
            price_version_id=price_version.id if price_version else None,
        )
        self.session.add(sale_line)
        self.session.flush()

        for allocation in allocations:
            self.session.add(
                SaleLineInventoryAllocation(
                    sale_line_id=sale_line.id,
                    inventory_batch_id=allocation.batch_id,
                    physical_units_allocated=allocation.physical_units,
                    unit_cost_snapshot=allocation.unit_cost,
                    total_cost_snapshot=allocation.total_cost,
                )
            )
        self.inventory.record_sale_movements(
            base_product_id=base_product.id,
            sale_line_id=sale_line.id,
            allocations=allocations,
            movement_date=sale_input.sale_date,
        )
        self.session.flush()
        return sale_line
