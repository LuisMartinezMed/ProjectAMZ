from __future__ import annotations

from datetime import date
from decimal import Decimal

from ecommerce_manager.app.services.inventory_service import InventoryService
from ecommerce_manager.app.services.sales_service import SalesService
from tests.conftest import make_listing


def test_fifo_allocation_across_batches(session):
    _, product, listing = make_listing(
        session,
        sku="FIFO",
        units_per_listing=1,
        unit_cost=Decimal("1.00"),
        initial_units=5,
    )
    inventory = InventoryService(session)
    inventory.create_batch(
        base_product_id=product.id,
        received_date=date(2026, 1, 10),
        physical_units=10,
        unit_landed_cost=Decimal("2.00"),
    )
    line = SalesService(session).add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=8,
        gross_revenue=Decimal("80.00"),
        net_received=Decimal("70.00"),
    )
    assert line.total_cogs_snapshot == Decimal("11.0000")
    assert line.supplier_unit_cost_snapshot == Decimal("1.3750")
    assert line.supplier_cost_per_listing_snapshot == Decimal("1.3750")
    assert line.total_landed_cost_per_listing_snapshot == Decimal("1.3750")
    assert [a.physical_units_allocated for a in line.inventory_allocations] == [5, 3]
    assert [a.unit_cost_snapshot for a in line.inventory_allocations] == [
        Decimal("1.0000"),
        Decimal("2.0000"),
    ]


def test_sale_decreases_inventory_and_records_movements(session):
    _, product, listing = make_listing(session, units_per_listing=4, initial_units=20)
    inventory = InventoryService(session)
    line = SalesService(session).add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=2,
        gross_revenue=Decimal("40.00"),
        net_received=Decimal("32.00"),
    )
    assert line.physical_units_consumed_snapshot == 8
    assert inventory.current_stock(product.id) == 12
    assert inventory.movement_stock(product.id) == 12
