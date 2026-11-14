import csv
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pricing_agent.models import PriceRecommendation
from pricing_agent.price_updater import CsvPriceUpdater


class PriceUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.path = Path(self.directory.name) / "products.csv"
        self.path.write_text(
            "product_id,name,cost,current_price,"
            "stock_quantity,demand_level,category\n"
            "P001,Headphones,55.00,89.00,11,high,Electronics\n",
            encoding="utf-8",
        )

        self.updater = CsvPriceUpdater(self.path)

    def make_recommendation(self, price="90.00", product_id="P001"):
        return PriceRecommendation(
            product_id=product_id,
            proposed_price=Decimal(price),
            reason="Test recommendation.",
        )

    def test_updates_price_and_preserves_other_fields(self):
        with self.path.open(newline="", encoding="utf-8") as handle:
            before = next(csv.DictReader(handle))

        changed = self.updater.apply_updates([
            self.make_recommendation(),
        ])

        with self.path.open(newline="", encoding="utf-8") as handle:
            after = next(csv.DictReader(handle))

        expected = {**before, "current_price": "90.00"}

        self.assertEqual(changed, 1)
        self.assertEqual(after, expected)

    def test_unchanged_price_does_not_rewrite_file(self):
        before = self.path.read_bytes()

        changed = self.updater.apply_updates([
            self.make_recommendation(price="89.00"),
        ])

        self.assertEqual(changed, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_product_prevents_all_updates(self):
        before = self.path.read_bytes()

        with self.assertRaises(ValueError):
            self.updater.apply_updates([
                self.make_recommendation(),
                self.make_recommendation(product_id="P999"),
            ])

        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_price_leaves_file_unchanged(self):
        before = self.path.read_bytes()

        with self.assertRaises(ValueError):
            self.updater.apply_updates([
                self.make_recommendation(price="-10.00"),
            ])

        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()