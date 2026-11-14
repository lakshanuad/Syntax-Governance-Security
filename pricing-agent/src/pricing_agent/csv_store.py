"""CSV input parsing, with actionable file and row errors."""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from .models import CompetitorPrice, DemandLevel, Product


class DataValidationError(ValueError):
    """The input data cannot be used for pricing."""


PRODUCT_COLUMNS = {
    "product_id", "name", "cost", "current_price", "stock_quantity", "demand_level"
}
COMPETITOR_COLUMNS = {"product_id", "competitor_name", "price"}


def _rows(path: Path, required: set[str]) -> list[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise DataValidationError(f"{path}: duplicate column names")
        missing = required - set(headers)
        if missing:
            raise DataValidationError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            location = f"{path}: line {reader.line_num}"
            if None in row or any(value is None for value in row.values()):
                raise DataValidationError(f"{location}: row does not match the header")
            cleaned = {key: value.strip() for key, value in row.items()}
            for column in sorted(required):
                if not cleaned[column]:
                    raise DataValidationError(f"{location}: {column} must not be empty")
            rows.append((reader.line_num, cleaned))
        return rows


def _money(value: str, column: str, location: str, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise DataValidationError(f"{location}: {column} must be a number") from None
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero):
        requirement = "non-negative" if allow_zero else "positive"
        raise DataValidationError(f"{location}: {column} must be finite and {requirement}")
    try:
        rounded = amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise DataValidationError(f"{location}: {column} is outside the supported numeric range") from None
    if amount != rounded:
        raise DataValidationError(f"{location}: {column} must have at most two decimal places")
    return amount


def load_products(path: Path) -> list[Product]:
    products = []
    seen = set()
    for line, row in _rows(path, PRODUCT_COLUMNS):
        location = f"{path}: line {line}"
        product_id = row["product_id"]
        if product_id in seen:
            raise DataValidationError(f"{location}: duplicate product_id {product_id!r}")
        seen.add(product_id)
        try:
            stock = int(row["stock_quantity"])
        except ValueError:
            raise DataValidationError(f"{location}: stock_quantity must be a non-negative integer") from None
        if stock < 0:
            raise DataValidationError(f"{location}: stock_quantity must be a non-negative integer")
        demand = row["demand_level"].lower()
        if demand not in {"low", "medium", "high"}:
            raise DataValidationError(f"{location}: demand_level must be low, medium, or high")
        products.append(Product(
            product_id=product_id,
            name=row["name"],
            cost=_money(row["cost"], "cost", location, allow_zero=True),
            current_price=_money(row["current_price"], "current_price", location),
            stock_quantity=stock,
            demand_level=cast(DemandLevel, demand),
        ))
    if not products:
        raise DataValidationError(f"{path}: at least one product is required")
    return products


def load_competitors(path: Path, products: list[Product]) -> list[CompetitorPrice]:
    product_ids = {product.product_id for product in products}
    competitors = []
    seen = set()
    for line, row in _rows(path, COMPETITOR_COLUMNS):
        location = f"{path}: line {line}"
        product_id = row["product_id"]
        if product_id not in product_ids:
            raise DataValidationError(f"{location}: unknown product_id {product_id!r}")
        key = (product_id, row["competitor_name"].casefold())
        if key in seen:
            raise DataValidationError(f"{location}: duplicate competitor for {product_id!r}")
        seen.add(key)
        competitors.append(CompetitorPrice(
            product_id=product_id,
            competitor_name=row["competitor_name"],
            price=_money(row["price"], "price", location),
        ))
    return competitors
