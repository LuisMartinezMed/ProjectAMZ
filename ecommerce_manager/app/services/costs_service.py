from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Type

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models import (
    ListingCostVersion,
    MarketplaceFeeVersion,
    PriceVersion,
    ProductCostVersion,
)
from ..utils.money import q4, to_decimal
from ..utils.validators import ValidationError, require_positive_int


class CostsService:
    def __init__(self, session: Session):
        self.session = session

    def create_product_cost_version(
        self,
        *,
        base_product_id: int,
        effective_from: date,
        supplier_id: Optional[int] = None,
        supplier_lot_cost: Decimal | int | str = 0,
        supplier_lot_units: int = 1,
        supplier_unit_cost: Decimal | int | str | None = None,
        inbound_shipping_cost_per_unit: Decimal | int | str = 0,
        warehouse_cost_per_unit: Decimal | int | str = 0,
        prep_cost_per_unit: Decimal | int | str = 0,
        other_cost_per_unit: Decimal | int | str = 0,
        total_landed_cost_per_unit: Decimal | int | str | None = None,
        notes: Optional[str] = None,
    ) -> ProductCostVersion:
        lot_units = require_positive_int(supplier_lot_units, "Supplier lot units")
        lot_cost = q4(supplier_lot_cost)
        unit_cost = q4(supplier_unit_cost if supplier_unit_cost is not None else lot_cost / lot_units)
        inbound = q4(inbound_shipping_cost_per_unit)
        warehouse = q4(warehouse_cost_per_unit)
        prep = q4(prep_cost_per_unit)
        other = q4(other_cost_per_unit)
        total = q4(total_landed_cost_per_unit if total_landed_cost_per_unit is not None else unit_cost + inbound + warehouse + prep + other)
        self._close_current_version(ProductCostVersion, "base_product_id", base_product_id, effective_from)
        version = ProductCostVersion(
            base_product_id=base_product_id,
            supplier_id=supplier_id,
            effective_from=effective_from,
            supplier_lot_cost=lot_cost,
            supplier_lot_units=lot_units,
            supplier_unit_cost=unit_cost,
            inbound_shipping_cost_per_unit=inbound,
            warehouse_cost_per_unit=warehouse,
            prep_cost_per_unit=prep,
            other_cost_per_unit=other,
            total_landed_cost_per_unit=total,
            notes=notes,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def create_listing_cost_version(
        self,
        *,
        listing_id: int,
        effective_from: date,
        cost_per_listing: Decimal | int | str = 0,
        warehouse_cost_per_listing: Decimal | int | str = 0,
        prep_cost_per_listing: Decimal | int | str = 0,
        inbound_shipping_cost_per_listing: Decimal | int | str = 0,
        other_cost_per_listing: Decimal | int | str = 0,
        total_landed_cost_per_listing: Decimal | int | str | None = None,
        notes: Optional[str] = None,
    ) -> ListingCostVersion:
        cost = q4(cost_per_listing)
        warehouse = q4(warehouse_cost_per_listing)
        prep = q4(prep_cost_per_listing)
        inbound = q4(inbound_shipping_cost_per_listing)
        other = q4(other_cost_per_listing)
        total = q4(total_landed_cost_per_listing if total_landed_cost_per_listing is not None else cost + warehouse + prep + inbound + other)
        self._close_current_version(ListingCostVersion, "listing_id", listing_id, effective_from)
        version = ListingCostVersion(
            listing_id=listing_id,
            effective_from=effective_from,
            cost_per_listing=cost,
            warehouse_cost_per_listing=warehouse,
            prep_cost_per_listing=prep,
            inbound_shipping_cost_per_listing=inbound,
            other_cost_per_listing=other,
            total_landed_cost_per_listing=total,
            notes=notes,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def create_marketplace_fee_version(
        self,
        *,
        listing_id: int,
        marketplace_id: int,
        effective_from: date,
        referral_fee: Decimal | int | str = 0,
        fba_fee: Decimal | int | str = 0,
        storage_fee: Decimal | int | str = 0,
        amazon_shipping_or_fulfillment_fee: Decimal | int | str = 0,
        other_marketplace_fee: Decimal | int | str = 0,
        estimated_total_fee: Decimal | int | str | None = None,
        fee_percentage: Decimal | int | str = 0,
        notes: Optional[str] = None,
    ) -> MarketplaceFeeVersion:
        referral = q4(referral_fee)
        fba = q4(fba_fee)
        storage = q4(storage_fee)
        shipping = q4(amazon_shipping_or_fulfillment_fee)
        other = q4(other_marketplace_fee)
        total = q4(estimated_total_fee if estimated_total_fee is not None else referral + fba + storage + shipping + other)
        self._close_current_version(
            MarketplaceFeeVersion,
            "listing_id",
            listing_id,
            effective_from,
            extra_filters=(MarketplaceFeeVersion.marketplace_id == marketplace_id,),
        )
        version = MarketplaceFeeVersion(
            listing_id=listing_id,
            marketplace_id=marketplace_id,
            effective_from=effective_from,
            referral_fee=referral,
            fba_fee=fba,
            storage_fee=storage,
            amazon_shipping_or_fulfillment_fee=shipping,
            other_marketplace_fee=other,
            estimated_total_fee=total,
            fee_percentage=q4(fee_percentage),
            notes=notes,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def create_price_version(
        self,
        *,
        listing_id: int,
        marketplace_id: int,
        effective_from: date,
        suggested_selling_price: Decimal | int | str,
        buybox_percentage: Decimal | int | str = 0,
        notes: Optional[str] = None,
    ) -> PriceVersion:
        self._close_current_version(
            PriceVersion,
            "listing_id",
            listing_id,
            effective_from,
            extra_filters=(PriceVersion.marketplace_id == marketplace_id,),
        )
        version = PriceVersion(
            listing_id=listing_id,
            marketplace_id=marketplace_id,
            effective_from=effective_from,
            suggested_selling_price=q4(suggested_selling_price),
            buybox_percentage=q4(buybox_percentage),
            notes=notes,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def get_product_cost_version(self, base_product_id: int, as_of: date) -> ProductCostVersion:
        version = self._get_effective(ProductCostVersion, "base_product_id", base_product_id, as_of)
        if version is None:
            raise ValidationError(f"No product cost version for product {base_product_id} on {as_of}")
        return version

    def get_listing_cost_version(self, listing_id: int, as_of: date) -> Optional[ListingCostVersion]:
        return self._get_effective(ListingCostVersion, "listing_id", listing_id, as_of)

    def get_marketplace_fee_version(
        self, listing_id: int, marketplace_id: int, as_of: date
    ) -> Optional[MarketplaceFeeVersion]:
        return self._get_effective(
            MarketplaceFeeVersion,
            "listing_id",
            listing_id,
            as_of,
            extra_filters=(MarketplaceFeeVersion.marketplace_id == marketplace_id,),
        )

    def get_price_version(self, listing_id: int, marketplace_id: int, as_of: date) -> Optional[PriceVersion]:
        return self._get_effective(
            PriceVersion,
            "listing_id",
            listing_id,
            as_of,
            extra_filters=(PriceVersion.marketplace_id == marketplace_id,),
        )

    def list_product_cost_versions(self, base_product_id: int) -> list[ProductCostVersion]:
        return self.session.scalars(
            select(ProductCostVersion)
            .where(ProductCostVersion.base_product_id == base_product_id)
            .order_by(ProductCostVersion.effective_from.desc(), ProductCostVersion.id.desc())
        ).all()

    def list_marketplace_fee_versions(
        self, listing_id: int, marketplace_id: int
    ) -> list[MarketplaceFeeVersion]:
        return self.session.scalars(
            select(MarketplaceFeeVersion)
            .where(
                MarketplaceFeeVersion.listing_id == listing_id,
                MarketplaceFeeVersion.marketplace_id == marketplace_id,
            )
            .order_by(MarketplaceFeeVersion.effective_from.desc(), MarketplaceFeeVersion.id.desc())
        ).all()

    def list_price_versions(self, listing_id: int, marketplace_id: int) -> list[PriceVersion]:
        return self.session.scalars(
            select(PriceVersion)
            .where(PriceVersion.listing_id == listing_id, PriceVersion.marketplace_id == marketplace_id)
            .order_by(PriceVersion.effective_from.desc(), PriceVersion.id.desc())
        ).all()

    def _close_current_version(
        self,
        model: Type,
        key_column_name: str,
        key_value: int,
        new_effective_from: date,
        *,
        extra_filters: tuple = (),
    ) -> None:
        key_column = getattr(model, key_column_name)
        future = self.session.scalar(
            select(model).where(
                key_column == key_value,
                model.effective_from >= new_effective_from,
                *extra_filters,
            )
        )
        if future is not None:
            raise ValidationError(
                f"Cannot create {model.__name__}; an existing version starts on or after {new_effective_from}"
            )
        current = self.session.scalar(
            select(model)
            .where(
                key_column == key_value,
                model.effective_to.is_(None),
                *extra_filters,
            )
            .order_by(model.effective_from.desc())
        )
        if current is not None:
            if current.effective_from >= new_effective_from:
                raise ValidationError("New effective date must be after the current version start date")
            current.effective_to = new_effective_from - timedelta(days=1)

    def _get_effective(
        self,
        model: Type,
        key_column_name: str,
        key_value: int,
        as_of: date,
        *,
        extra_filters: tuple = (),
    ):
        key_column = getattr(model, key_column_name)
        return self.session.scalar(
            select(model)
            .where(
                key_column == key_value,
                model.effective_from <= as_of,
                or_(model.effective_to.is_(None), model.effective_to >= as_of),
                *extra_filters,
            )
            .order_by(model.effective_from.desc())
        )
