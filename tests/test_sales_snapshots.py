from __future__ import annotations

from datetime import date
from decimal import Decimal

from ecommerce_manager.app.services.costs_service import CostsService
from ecommerce_manager.app.services.reports_service import ReportsService
from ecommerce_manager.app.services.sales_service import SalesService
from tests.conftest import make_listing


def test_sale_keeps_old_product_cost_after_cost_change(session):
    _, product, listing = make_listing(session, units_per_listing=1, unit_cost=Decimal("2.00"))
    sales = SalesService(session)
    line = sales.add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=2,
        gross_revenue=Decimal("20.00"),
        net_received=Decimal("14.00"),
    )
    original_profit = line.profit_snapshot
    CostsService(session).create_product_cost_version(
        base_product_id=product.id,
        effective_from=date(2026, 6, 1),
        supplier_lot_cost=Decimal("9.00"),
        supplier_lot_units=1,
        supplier_unit_cost=Decimal("9.00"),
        total_landed_cost_per_unit=Decimal("9.00"),
    )
    session.flush()
    assert line.supplier_unit_cost_snapshot == Decimal("2.0000")
    assert line.total_cogs_snapshot == Decimal("4.0000")
    assert line.profit_snapshot == original_profit


def test_sale_keeps_old_fee_after_fee_change(session):
    marketplace, _, listing = make_listing(session, units_per_listing=1, fee=Decimal("1.25"))
    line = SalesService(session).add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=2,
        gross_revenue=Decimal("20.00"),
        net_received=None,
    )
    old_fee_version_id = line.fee_version_id
    CostsService(session).create_marketplace_fee_version(
        listing_id=listing.id,
        marketplace_id=marketplace.id,
        effective_from=date(2026, 6, 1),
        estimated_total_fee=Decimal("8.00"),
    )
    session.flush()
    assert line.fee_version_id == old_fee_version_id
    assert line.marketplace_fee_snapshot == Decimal("2.5000")
    assert line.net_received == Decimal("17.5000")
    assert line.net_received_estimated is True


def test_same_sku_same_date_can_have_different_prices(session):
    _, _, listing = make_listing(session, units_per_listing=1)
    sales = SalesService(session)
    first = sales.add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=1,
        gross_revenue=Decimal("10.00"),
        net_received=Decimal("7.00"),
    )
    second = sales.add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=1,
        gross_revenue=Decimal("12.00"),
        net_received=Decimal("8.50"),
    )
    assert first.id != second.id
    assert first.selling_price_per_listing_snapshot == Decimal("10.0000")
    assert second.selling_price_per_listing_snapshot == Decimal("12.0000")


def test_listing_quantity_converts_to_physical_units(session):
    _, _, listing = make_listing(session, units_per_listing=8, initial_units=100)
    line = SalesService(session).add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=2,
        gross_revenue=Decimal("40.00"),
        net_received=Decimal("30.00"),
    )
    assert line.physical_units_consumed_snapshot == 16


def test_dashboard_historical_profit_does_not_change_after_cost_update(session):
    _, product, listing = make_listing(session, units_per_listing=1, unit_cost=Decimal("2.00"))
    SalesService(session).add_manual_sale(
        sale_date=date(2026, 5, 1),
        sku=listing.sku,
        quantity_listings_sold=2,
        gross_revenue=Decimal("20.00"),
        net_received=Decimal("14.00"),
    )
    before = ReportsService(session).dashboard_metrics(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
    )
    CostsService(session).create_product_cost_version(
        base_product_id=product.id,
        effective_from=date(2026, 6, 1),
        supplier_lot_cost=Decimal("9.00"),
        supplier_lot_units=1,
        supplier_unit_cost=Decimal("9.00"),
        total_landed_cost_per_unit=Decimal("9.00"),
    )
    after = ReportsService(session).dashboard_metrics(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
    )
    assert after.total_profit == before.total_profit == Decimal("10.0000")
