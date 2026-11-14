"""Typed records shared by storage and the future pricing agent."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DemandLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    cost: Decimal
    current_price: Decimal
    stock_quantity: int
    demand_level: DemandLevel


@dataclass(frozen=True)
class CompetitorPrice:
    product_id: str
    competitor_name: str
    price: Decimal

@dataclass(frozen=True)
class PriceRecommendation:
    product_id: str
    proposed_price: Decimal
    reason: str