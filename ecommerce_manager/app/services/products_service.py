from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import BaseProduct, Listing, Marketplace, Supplier
from ..utils.validators import ValidationError, require_positive_int, require_text


logger = logging.getLogger(__name__)
PACK_PATTERNS = (
    re.compile(r"\bpack\s+of\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*[- ]?pack\b", re.IGNORECASE),
    re.compile(r"\bcase\s+of\s+(\d+)\b", re.IGNORECASE),
)


def infer_units_per_listing(name: str | None) -> int:
    if not name:
        return 1
    for pattern in PACK_PATTERNS:
        match = pattern.search(name)
        if match:
            return max(1, int(match.group(1)))
    return 1


class ProductsService:
    def __init__(self, session: Session):
        self.session = session

    def get_marketplace(self, name: str = "Amazon") -> Marketplace:
        marketplace = self.session.scalar(select(Marketplace).where(Marketplace.name == name))
        if marketplace is None:
            marketplace = Marketplace(name=name, status="active")
            self.session.add(marketplace)
            self.session.flush()
        return marketplace

    def create_supplier(
        self,
        name: str,
        *,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        default_lead_time_days: Optional[int] = None,
        default_shipping_days: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Supplier:
        supplier = Supplier(
            name=require_text(name, "Supplier name"),
            contact_name=contact_name,
            email=email,
            phone=phone,
            website=website,
            default_lead_time_days=default_lead_time_days,
            default_shipping_days=default_shipping_days,
            notes=notes,
        )
        self.session.add(supplier)
        self.session.flush()
        return supplier

    def list_suppliers(self) -> list[Supplier]:
        return self.session.scalars(select(Supplier).order_by(Supplier.name)).all()

    def list_base_products(self, *, active_only: bool = False) -> list[BaseProduct]:
        stmt = select(BaseProduct).order_by(BaseProduct.name)
        if active_only:
            stmt = stmt.where(BaseProduct.status == "active")
        return self.session.scalars(stmt).all()

    def list_listings(self, *, active_only: bool = False) -> list[Listing]:
        stmt = select(Listing).join(Listing.base_product).order_by(Listing.sku)
        if active_only:
            stmt = stmt.where(Listing.status == "active")
        return self.session.scalars(stmt).all()

    def create_base_product(
        self,
        name: str,
        *,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        upc: Optional[str] = None,
        supplier_id: Optional[int] = None,
        supplier_product_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> BaseProduct:
        product = BaseProduct(
            name=require_text(name, "Product name"),
            brand=brand,
            category=category,
            upc=upc,
            supplier_id=supplier_id,
            supplier_product_url=supplier_product_url,
            notes=notes,
            status="active",
        )
        self.session.add(product)
        self.session.flush()
        logger.info("Created base product id=%s name=%r", product.id, product.name)
        return product

    def create_listing(
        self,
        *,
        marketplace_id: int,
        base_product_id: int,
        sku: str,
        listing_name: str,
        asin: Optional[str] = None,
        units_per_listing: Optional[int] = None,
        amazon_product_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Listing:
        normalized_sku = require_text(sku, "SKU")
        units = units_per_listing or infer_units_per_listing(listing_name)
        units = require_positive_int(units, "Units per listing")
        existing = self.session.scalar(
            select(Listing).where(
                Listing.marketplace_id == marketplace_id,
                Listing.sku == normalized_sku,
            )
        )
        if existing:
            raise ValidationError(f"SKU already exists for marketplace: {normalized_sku}")
        listing = Listing(
            marketplace_id=marketplace_id,
            base_product_id=base_product_id,
            sku=normalized_sku,
            asin=asin.strip() if asin else None,
            listing_name=require_text(listing_name, "Listing name"),
            units_per_listing=units,
            amazon_product_url=amazon_product_url,
            notes=notes,
            status="active",
        )
        self.session.add(listing)
        self.session.flush()
        logger.info(
            "Created listing id=%s sku=%r base_product_id=%s",
            listing.id,
            listing.sku,
            listing.base_product_id,
        )
        return listing

    def find_listing(
        self,
        *,
        sku: Optional[str] = None,
        asin: Optional[str] = None,
        marketplace_id: Optional[int] = None,
        marketplace_name: str = "Amazon",
    ) -> Listing:
        if not sku and not asin:
            raise ValidationError("SKU or ASIN is required")
        if marketplace_id is None:
            marketplace_id = self.get_marketplace(marketplace_name).id
        conditions = []
        if sku:
            conditions.append(Listing.sku == sku.strip())
        if asin:
            conditions.append(Listing.asin == asin.strip())
        listing = self.session.scalar(
            select(Listing).where(Listing.marketplace_id == marketplace_id, or_(*conditions))
        )
        if listing is None:
            key = sku or asin
            raise ValidationError(f"Listing not found: {key}")
        return listing

    def deactivate_listing(self, listing_id: int) -> Listing:
        listing = self.session.get(Listing, listing_id)
        if listing is None:
            raise ValidationError(f"Listing not found: {listing_id}")
        listing.status = "inactive"
        return listing

    def update_listing(
        self,
        listing_id: int,
        *,
        base_product_name: str,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        supplier_product_url: Optional[str] = None,
        sku: str,
        asin: Optional[str] = None,
        listing_name: str,
        units_per_listing: int,
        amazon_product_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Listing:
        listing = self.session.get(Listing, listing_id)
        if listing is None:
            raise ValidationError(f"Listing not found: {listing_id}")
        normalized_sku = require_text(sku, "SKU")
        existing = self.session.scalar(
            select(Listing).where(
                Listing.marketplace_id == listing.marketplace_id,
                Listing.sku == normalized_sku,
                Listing.id != listing.id,
            )
        )
        if existing:
            raise ValidationError(f"SKU already exists for marketplace: {normalized_sku}")
        listing.base_product.name = require_text(base_product_name, "Product name")
        listing.base_product.brand = brand
        listing.base_product.category = category
        listing.base_product.supplier_product_url = supplier_product_url
        listing.sku = normalized_sku
        listing.asin = asin.strip() if asin else None
        listing.listing_name = require_text(listing_name, "Listing name")
        listing.units_per_listing = require_positive_int(units_per_listing, "Units per listing")
        listing.amazon_product_url = amazon_product_url
        listing.notes = notes
        self.session.flush()
        return listing
