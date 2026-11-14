"""Shared pricing workflow for the CLI and local web interface."""

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .csv_store import load_competitors, load_products
from .models import CompetitorPrice, PriceRecommendation, Product
from .price_updater import CsvPriceUpdater
from .recommendation import validate_recommendation

Proposer = Callable[[Product, list[CompetitorPrice]], PriceRecommendation]


class PricingService:
    def __init__(self, products_path: Path, competitors_path: Path, proposer: Proposer | None = None):
        self.products_path = products_path.resolve()
        self.competitors_path = competitors_path.resolve()
        self.proposer = proposer

    def inventory(self) -> list[dict]:
        return [
            {
                "product_id": product.product_id,
                "name": product.name,
                "cost": f"{product.cost:.2f}",
                "current_price": f"{product.current_price:.2f}",
                "stock_quantity": product.stock_quantity,
                "demand_level": product.demand_level,
            }
            for product in load_products(self.products_path)
        ]

    def run(self, on_progress: Callable[[str], None] | None = None) -> dict:
        products = load_products(self.products_path)
        competitors = load_competitors(self.competitors_path, products)
        proposer = self.proposer
        if proposer is None:
            from .agent import propose_price

            proposer = propose_price

        report = on_progress or (lambda message: None)
        recommendations = []
        decisions = []
        for index, product in enumerate(products, 1):
            report(f"Analyzing {product.name} ({index}/{len(products)})")
            recommendation = proposer(product, competitors)
            # Check the response against the requested product before recording it.
            recommendation = validate_recommendation({
                "product_id": recommendation.product_id,
                "proposed_price": str(recommendation.proposed_price),
                "reason": recommendation.reason,
            }, product)
            recommendations.append(recommendation)
            decisions.append({
                "product_id": product.product_id,
                "name": product.name,
                "old_price": f"{product.current_price:.2f}",
                "new_price": f"{recommendation.proposed_price:.2f}",
                "changed": product.current_price != recommendation.proposed_price,
                "reason": recommendation.reason,
            })

        report("Saving validated prices")
        changed = CsvPriceUpdater(self.products_path).apply_updates(recommendations)
        return {
            "id": uuid4().hex,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "changed": changed,
            "unchanged": len(products) - changed,
            "decisions": decisions,
        }
