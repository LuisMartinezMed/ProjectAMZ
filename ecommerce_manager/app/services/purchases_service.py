from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from ..models import PurchaseOrder, PurchaseOrderLine
from ..utils.money import q4
from ..utils.validators import require_positive_int
from .inventory_service import InventoryService


class PurchasesService:
    def __init__(self, session: Session):
        self.session = session
        self.inventory = InventoryService(session)

    def create_purchase_order(
        self,
        *,
        supplier_id: int,
        order_date: date,
        expected_arrival_date: Optional[date] = None,
        subtotal: Decimal | int | str = 0,
        shipping_cost: Decimal | int | str = 0,
        other_cost: Decimal | int | str = 0,
        notes: Optional[str] = None,
    ) -> PurchaseOrder:
        subtotal_d = q4(subtotal)
        shipping_d = q4(shipping_cost)
        other_d = q4(other_cost)
        purchase_order = PurchaseOrder(
            supplier_id=supplier_id,
            order_date=order_date,
            expected_arrival_date=expected_arrival_date,
            status="draft",
            subtotal=subtotal_d,
            shipping_cost=shipping_d,
            other_cost=other_d,
            total_cost=q4(subtotal_d + shipping_d + other_d),
            notes=notes,
        )
        self.session.add(purchase_order)
        self.session.flush()
        return purchase_order

    def list_purchase_orders(self) -> list[PurchaseOrder]:
        return self.session.scalars(
            select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        ).all()

    def list_purchase_order_lines(self, purchase_order_id: int | None = None) -> list[PurchaseOrderLine]:
        stmt = select(PurchaseOrderLine).order_by(PurchaseOrderLine.id.desc())
        if purchase_order_id is not None:
            stmt = stmt.where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
        return self.session.scalars(stmt).all()

    def add_line(
        self,
        *,
        purchase_order_id: int,
        base_product_id: int,
        ordered_physical_units: int,
        supplier_lot_cost: Decimal | int | str,
        supplier_lot_units: int,
        inbound_shipping_allocated: Decimal | int | str = 0,
        notes: Optional[str] = None,
    ) -> PurchaseOrderLine:
        lot_units = require_positive_int(supplier_lot_units, "Supplier lot units")
        ordered_units = require_positive_int(ordered_physical_units, "Ordered physical units")
        lot_cost = q4(supplier_lot_cost)
        line = PurchaseOrderLine(
            purchase_order_id=purchase_order_id,
            base_product_id=base_product_id,
            ordered_physical_units=ordered_units,
            supplier_lot_cost=lot_cost,
            supplier_lot_units=lot_units,
            supplier_unit_cost=q4(lot_cost / lot_units),
            inbound_shipping_allocated=q4(inbound_shipping_allocated),
            received_physical_units=0,
            notes=notes,
        )
        self.session.add(line)
        self.session.flush()
        return line

    def receive_line(
        self,
        *,
        purchase_order_line_id: int,
        received_date: date,
        received_physical_units: Optional[int] = None,
        warehouse_location: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        line = self.session.get(PurchaseOrderLine, purchase_order_line_id)
        if line is None:
            raise ValueError(f"Purchase order line not found: {purchase_order_line_id}")
        units = received_physical_units or line.ordered_physical_units
        per_unit_shipping = q4(line.inbound_shipping_allocated / units) if units else q4(0)
        unit_landed_cost = q4(line.supplier_unit_cost + per_unit_shipping)
        batch = self.inventory.create_batch(
            base_product_id=line.base_product_id,
            purchase_order_line_id=line.id,
            received_date=received_date,
            physical_units=units,
            unit_landed_cost=unit_landed_cost,
            warehouse_location=warehouse_location,
            notes=notes,
        )
        line.received_physical_units += units
        purchase_order = line.purchase_order
        if all(item.received_physical_units >= item.ordered_physical_units for item in purchase_order.lines):
            purchase_order.status = "received"
            purchase_order.received_date = received_date
        else:
            purchase_order.status = "partially_received"
        self.session.flush()
        return batch
