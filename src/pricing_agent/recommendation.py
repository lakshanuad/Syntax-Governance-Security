from decimal import Decimal, InvalidOperation

from .models import PriceRecommendation, Product


def validate_recommendation(
    data: dict,
    product: Product,
) -> PriceRecommendation:
    if not isinstance(data, dict):
        raise ValueError("Recommendation must be an object.")

    if data.get("product_id") != product.product_id:
        raise ValueError("Recommendation has the wrong product ID.")

    price_text = data.get("proposed_price")

    if not isinstance(price_text, str):
        raise ValueError("Proposed price must be a string.")

    try:
        price = Decimal(price_text)
    except InvalidOperation:
        raise ValueError("Proposed price must be numeric.") from None

    if not price.is_finite() or price <= 0:
        raise ValueError("Proposed price must be finite and positive.")

    try:
        rounded_price = price.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError("Proposed price is outside the supported range.") from None

    if price != rounded_price:
        raise ValueError("Proposed price must have at most two decimal places.")

    reason = data.get("reason")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Recommendation must include a reason.")

    return PriceRecommendation(
        product_id=product.product_id,
        proposed_price=price,
        reason=reason.strip(),
    )