from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AppSetting, InventoryBatch, InventoryMovement, StockAdjustment
from ..utils.money import q4
from ..utils.validators import ValidationError, require_positive_int


@dataclass(frozen=True)
class InventoryAllocation:
    batch_id: int
    physical_units: int
    unit_cost: Decimal
    total_cost: Decimal


class InventoryService:
    def __init__(self, session: Session):
        self.session = session

    def create_initial_stock(
        self,
        *,
        base_product_id: int,
        received_date: date,
        physical_units: int,
        unit_landed_cost: Decimal | int | str,
        warehouse_location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InventoryBatch:
        return self.create_batch(
            base_product_id=base_product_id,
            received_date=received_date,
            physical_units=physical_units,
            unit_landed_cost=unit_landed_cost,
            movement_type="initial_stock",
            warehouse_location=warehouse_location,
            notes=notes,
        )

    def create_batch(
        self,
        *,
        base_product_id: int,
        received_date: date,
        physical_units: int,
        unit_landed_cost: Decimal | int | str,
        movement_type: str = "purchase_received",
        purchase_order_line_id: Optional[int] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        warehouse_location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InventoryBatch:
        units = require_positive_int(physical_units, "Physical units")
        batch = InventoryBatch(
            base_product_id=base_product_id,
            purchase_order_line_id=purchase_order_line_id,
            received_date=received_date,
            initial_physical_units=units,
            remaining_physical_units=units,
            unit_landed_cost=q4(unit_landed_cost),
            warehouse_location=warehouse_location,
            status="available",
            notes=notes,
        )
        self.session.add(batch)
        self.session.flush()
        self._record_movement(
            base_product_id=base_product_id,
            inventory_batch_id=batch.id,
            movement_date=received_date,
            movement_type=movement_type,
            physical_quantity_change=units,
            reference_type=reference_type or ("purchase_order_line" if purchase_order_line_id else None),
            reference_id=reference_id or purchase_order_line_id,
            notes=notes,
        )
        return batch

    def current_stock(self, base_product_id: int) -> int:
        stock = self.session.scalar(
            select(func.coalesce(func.sum(InventoryBatch.remaining_physical_units), 0)).where(
                InventoryBatch.base_product_id == base_product_id
            )
        )
        return int(stock or 0)

    def movement_stock(self, base_product_id: int) -> int:
        stock = self.session.scalar(
            select(func.coalesce(func.sum(InventoryMovement.physical_quantity_change), 0)).where(
                InventoryMovement.base_product_id == base_product_id
            )
        )
        return int(stock or 0)

    def available_listing_stock(self, base_product_id: int, units_per_listing: int) -> int:
        units = require_positive_int(units_per_listing, "Units per listing")
        return self.current_stock(base_product_id) // units

    def allocate_fifo(
        self,
        *,
        base_product_id: int,
        physical_units: int,
        movement_date: date,
    ) -> list[InventoryAllocation]:
        allocations = self.preview_fifo_allocation(
            base_product_id=base_product_id,
            physical_units=physical_units,
        )
        batch_by_id = {
            batch.id: batch
            for batch in self.session.scalars(
                select(InventoryBatch).where(
                    InventoryBatch.id.in_([allocation.batch_id for allocation in allocations])
                )
            ).all()
        }
        for allocation in allocations:
            batch = batch_by_id[allocation.batch_id]
            batch.remaining_physical_units -= allocation.physical_units
            if batch.remaining_physical_units == 0:
                batch.status = "depleted"
        return allocations

    def preview_fifo_allocation(
        self,
        *,
        base_product_id: int,
        physical_units: int,
    ) -> list[InventoryAllocation]:
        needed = require_positive_int(physical_units, "Physical units to allocate")
        batches = self.session.scalars(
            select(InventoryBatch)
            .where(
                InventoryBatch.base_product_id == base_product_id,
                InventoryBatch.remaining_physical_units > 0,
            )
            .order_by(InventoryBatch.received_date.asc(), InventoryBatch.id.asc())
        ).all()
        available = sum(batch.remaining_physical_units for batch in batches)
        if available < needed and not self.allow_negative_inventory():
            raise ValidationError(
                f"Insufficient inventory for product {base_product_id}: need {needed}, available {available}"
            )

        allocations: list[InventoryAllocation] = []
        remaining = needed
        for batch in batches:
            if remaining <= 0:
                break
            units = min(batch.remaining_physical_units, remaining)
            total_cost = q4(batch.unit_landed_cost * units)
            allocations.append(
                InventoryAllocation(
                    batch_id=batch.id,
                    physical_units=units,
                    unit_cost=q4(batch.unit_landed_cost),
                    total_cost=total_cost,
                )
            )
            remaining -= units

        if remaining > 0:
            raise ValidationError("Negative inventory sales are not implemented for FIFO allocation yet")
        return allocations

    def record_sale_movements(
        self,
        *,
        base_product_id: int,
        sale_line_id: int,
        allocations: list[InventoryAllocation],
        movement_date: date,
    ) -> None:
        for allocation in allocations:
            self._record_movement(
                base_product_id=base_product_id,
                inventory_batch_id=allocation.batch_id,
                movement_date=movement_date,
                movement_type="sale",
                physical_quantity_change=-allocation.physical_units,
                reference_type="sale_line",
                reference_id=sale_line_id,
            )

    def adjust_stock(
        self,
        *,
        base_product_id: int,
        adjustment_date: date,
        physical_quantity_change: int,
        reason: str,
        notes: Optional[str] = None,
    ) -> StockAdjustment:
        adjustment = StockAdjustment(
            base_product_id=base_product_id,
            adjustment_date=adjustment_date,
            physical_quantity_change=physical_quantity_change,
            reason=reason,
            notes=notes,
        )
        self.session.add(adjustment)
        self.session.flush()
        if physical_quantity_change > 0:
            batch = InventoryBatch(
                base_product_id=base_product_id,
                received_date=adjustment_date,
                initial_physical_units=physical_quantity_change,
                remaining_physical_units=physical_quantity_change,
                unit_landed_cost=q4(0),
                status="available",
                notes=f"Adjustment: {reason}",
            )
            self.session.add(batch)
            self.session.flush()
            self._record_movement(
                base_product_id=base_product_id,
                inventory_batch_id=batch.id,
                movement_date=adjustment_date,
                movement_type="adjustment",
                physical_quantity_change=physical_quantity_change,
                reference_type="stock_adjustment",
                reference_id=adjustment.id,
                notes=notes,
            )
        elif physical_quantity_change < 0:
            allocations = self.allocate_fifo(
                base_product_id=base_product_id,
                physical_units=abs(physical_quantity_change),
                movement_date=adjustment_date,
            )
            for allocation in allocations:
                self._record_movement(
                    base_product_id=base_product_id,
                    inventory_batch_id=allocation.batch_id,
                    movement_date=adjustment_date,
                    movement_type="adjustment",
                    physical_quantity_change=-allocation.physical_units,
                    reference_type="stock_adjustment",
                    reference_id=adjustment.id,
                    notes=notes,
                )
        return adjustment

    def allow_negative_inventory(self) -> bool:
        setting = self.session.scalar(select(AppSetting).where(AppSetting.key == "allow_negative_inventory"))
        return bool(setting and setting.value.strip().lower() in {"true", "1", "yes", "y"})

    def _record_movement(
        self,
        *,
        base_product_id: int,
        inventory_batch_id: Optional[int],
        movement_date: date,
        movement_type: str,
        physical_quantity_change: int,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            base_product_id=base_product_id,
            inventory_batch_id=inventory_batch_id,
            movement_date=movement_date,
            movement_type=movement_type,
            physical_quantity_change=physical_quantity_change,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
        )
        self.session.add(movement)
        self.session.flush()
        return movement
