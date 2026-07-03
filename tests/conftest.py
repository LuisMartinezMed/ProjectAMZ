from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ecommerce_manager.app.database import seed_defaults
from ecommerce_manager.app.models import Base
from ecommerce_manager.app.services.costs_service import CostsService
from ecommerce_manager.app.services.inventory_service import InventoryService
from ecommerce_manager.app.services.products_service import ProductsService


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_defaults(session)
        session.commit()
    with Session(engine) as session:
        yield session


def make_listing(
    session,
    *,
    sku: str = "SKU-1",
    asin: str = "B000TEST",
    units_per_listing: int = 1,
    unit_cost: Decimal = Decimal("2.00"),
    initial_units: int = 100,
    fee: Decimal = Decimal("1.00"),
):
    products = ProductsService(session)
    costs = CostsService(session)
    inventory = InventoryService(session)
    marketplace = products.get_marketplace("Amazon")
    product = products.create_base_product(name=f"Product {sku}")
    listing = products.create_listing(
        marketplace_id=marketplace.id,
        base_product_id=product.id,
        sku=sku,
        asin=asin,
        listing_name=f"Product {sku} Pack of {units_per_listing}",
        units_per_listing=units_per_listing,
    )
    costs.create_product_cost_version(
        base_product_id=product.id,
        effective_from=date(2026, 1, 1),
        supplier_lot_cost=unit_cost,
        supplier_lot_units=1,
        supplier_unit_cost=unit_cost,
        total_landed_cost_per_unit=unit_cost,
    )
    costs.create_marketplace_fee_version(
        listing_id=listing.id,
        marketplace_id=marketplace.id,
        effective_from=date(2026, 1, 1),
        estimated_total_fee=fee,
    )
    costs.create_price_version(
        listing_id=listing.id,
        marketplace_id=marketplace.id,
        effective_from=date(2026, 1, 1),
        suggested_selling_price=Decimal("10.00"),
    )
    inventory.create_initial_stock(
        base_product_id=product.id,
        received_date=date(2026, 1, 1),
        physical_units=initial_units,
        unit_landed_cost=unit_cost,
    )
    session.flush()
    return marketplace, product, listing

