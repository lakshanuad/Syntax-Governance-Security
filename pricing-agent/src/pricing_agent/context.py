from .models import CompetitorPrice, Product


def build_product_context(
    product: Product,
    competitors: list[CompetitorPrice],
) -> dict:
    matching_competitors = [
        competitor
        for competitor in competitors
        if competitor.product_id == product.product_id
    ]

    return {
        "product_id": product.product_id,
        "name": product.name,
        "cost": str(product.cost),
        "current_price": str(product.current_price),
        "stock_quantity": product.stock_quantity,
        "demand_level": product.demand_level,
        "competitor_prices": [
            {
                "competitor_name": competitor.competitor_name,
                "price": str(competitor.price),
            }
            for competitor in matching_competitors
        ],
    }
