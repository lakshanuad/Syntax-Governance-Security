"""Inspect pricing inputs or run AI recommendations and CSV updates."""
import argparse
import csv
import sys
from pathlib import Path

from .config import DEFAULT_COMPETITORS, DEFAULT_PRODUCTS, load_environment
from .csv_store import DataValidationError, load_competitors, load_products
from .service import PricingService


def run_pricing(
    products_path: Path,
    competitors_path: Path,
) -> int:
    from google.genai import errors
    from httpx import HTTPError

    try:
        result = PricingService(products_path, competitors_path).run(print)
    except (errors.APIError, HTTPError, ValueError, OSError, UnicodeError, csv.Error) as error:
        print(f"Pricing failed: {error}", file=sys.stderr)
        return 1
    for decision in result["decisions"]:
        print(f"{decision['product_id']}: {decision['name']}")
        print(f"  Previous: {decision['old_price']} | Current: {decision['new_price']}")
        print(f"  Reason: {decision['reason']}")
    print(
        f"\nCompleted: {result['changed']} prices updated,"
        f" {result['unchanged']} unchanged."
    )
    return 0

def main(argv: list[str] | None = None) -> int:
    load_environment()
    parser = argparse.ArgumentParser(description="Inspect inputs or run AI dynamic pricing.")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--competitors", type=Path, default=DEFAULT_COMPETITORS)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Request AI recommendations and update product prices.",
    )
    args = parser.parse_args(argv)
    try:
        products = load_products(args.products)
        competitors = load_competitors(args.competitors, products)
    except (DataValidationError, OSError, UnicodeError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if args.run:
        return run_pricing(
            args.products,
            args.competitors,
        )

    print("Dynamic Pricing Agent - input inspection")
    for product in products:
        matches = [item for item in competitors if item.product_id == product.product_id]
        print(f"\n{product.product_id} | {product.name}")
        print(f"  Cost: {product.cost:.2f} | Current price: {product.current_price:.2f}")
        print(f"  Stock: {product.stock_quantity} | Demand: {product.demand_level}")
        if matches:
            for competitor in matches:
                print(f"  Competitor: {competitor.competitor_name} | {competitor.price:.2f}")
        else:
            print("  No competitor prices available.")
    print(f"\nLoaded {len(products)} products and {len(competitors)} competitor prices.")
    print("Input inspection complete. Use --run to request AI pricing and apply updates.")
    return 0
