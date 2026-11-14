import unittest
from decimal import Decimal

from pricing_agent.models import Product
from pricing_agent.recommendation import validate_recommendation


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.product = Product(
            product_id="P001",
            name="Wireless Headphones",
            cost=Decimal("55.00"),
            current_price=Decimal("89.00"),
            stock_quantity=11,
            demand_level="high",
        )

        self.valid_data = {
            "product_id": "P001",
            "proposed_price": "89.00",
            "reason": "The current price remains competitive.",
        }

    def test_accepts_valid_recommendation(self):
        result = validate_recommendation(
            self.valid_data,
            self.product,
        )

        self.assertEqual(result.product_id, "P001")
        self.assertEqual(result.proposed_price, Decimal("89.00"))

    def test_rejects_wrong_product(self):
        data = {**self.valid_data, "product_id": "P999"}

        with self.assertRaises(ValueError):
            validate_recommendation(data, self.product)

    def test_rejects_invalid_prices(self):
        for price in [
            "not-a-price",
            "NaN",
            "Infinity",
            "-10.00",
            "0.00",
            "89.001",
            89.00,
        ]:
            with self.subTest(price=price):
                data = {**self.valid_data, "proposed_price": price}

                with self.assertRaises(ValueError):
                    validate_recommendation(data, self.product)

    def test_rejects_empty_reason(self):
        data = {**self.valid_data, "reason": "   "}

        with self.assertRaises(ValueError):
            validate_recommendation(data, self.product)


if __name__ == "__main__":
    unittest.main()