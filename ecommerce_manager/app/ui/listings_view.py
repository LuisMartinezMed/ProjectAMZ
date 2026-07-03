from __future__ import annotations

from .products_view import ProductsView


class ListingsView(ProductsView):
    """Compatibility view for callers that expect a listings-specific widget."""

