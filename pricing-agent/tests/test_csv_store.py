import contextlib
import io
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from pricing_agent.cli import main
from pricing_agent.csv_store import DataValidationError, load_competitors, load_products


HEADER = "product_id,name,cost,current_price,stock_quantity,demand_level\n"
VALID_ROW = "P001,Mouse,12.50,20.00,5,high\n"


class CsvStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.products = Path(self.directory.name) / "products.csv"
        self.competitors = Path(self.directory.name) / "competitors.csv"
        self.products.write_text(HEADER + VALID_ROW, encoding="utf-8")
        self.competitors.write_text("product_id,competitor_name,price\nP001,Shop A,19.50\n", encoding="utf-8")

    def test_loads_money_as_decimal_and_matches_competitors(self):
        products = load_products(self.products)
        self.assertEqual(products[0].cost, Decimal("12.50"))
        self.assertEqual(load_competitors(self.competitors, products)[0].price, Decimal("19.50"))

    def test_rejects_invalid_product_rows(self):
        rows = [
            "P001,Mouse,NaN,20.00,5,high\n",
            "P001,Mouse,12.50,Infinity,5,high\n",
            "P001,Mouse,12.50,0,5,high\n",
            "P001,Mouse,12.50,20.001,5,high\n",
            "P001,Mouse,1e1000,20.00,5,high\n",
            "P001,Mouse,12.50,20.00,-1,high\n",
            "P001,Mouse,12.50,20.00,1.5,high\n",
            "P001,Mouse,12.50,20.00,5,unknown\n",
            "P001,,12.50,20.00,5,high\n",
            "P001,Mouse,12.50,20.00,5\n",
            "P001,Mouse,12.50,20.00,5,high,extra\n",
            VALID_ROW + VALID_ROW,
        ]
        for row in rows:
            with self.subTest(row=row):
                self.products.write_text(HEADER + row, encoding="utf-8")
                with self.assertRaises(DataValidationError):
                    load_products(self.products)

    def test_rejects_missing_columns_and_empty_products(self):
        for content in ["product_id,name\nP001,Mouse\n", HEADER, ""]:
            with self.subTest(content=content):
                self.products.write_text(content, encoding="utf-8")
                with self.assertRaises(DataValidationError):
                    load_products(self.products)

    def test_rejects_unknown_or_duplicate_competitors(self):
        products = load_products(self.products)
        for rows in ["P999,Shop A,19.50\n", "P001,Shop A,19.50\nP001,shop a,18.00\n"]:
            with self.subTest(rows=rows):
                self.competitors.write_text("product_id,competitor_name,price\n" + rows, encoding="utf-8")
                with self.assertRaises(DataValidationError):
                    load_competitors(self.competitors, products)

    def test_allows_no_competitor_observations(self):
        self.competitors.write_text("product_id,competitor_name,price\n", encoding="utf-8")
        self.assertEqual(load_competitors(self.competitors, load_products(self.products)), [])

    def test_cli_displays_inputs_without_changing_files(self):
        before = self.products.read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--products", str(self.products), "--competitors", str(self.competitors)])
        self.assertEqual(result, 0)
        self.assertIn("Shop A", output.getvalue())
        self.assertEqual(self.products.read_bytes(), before)

    def test_cli_reports_missing_file(self):
        with contextlib.redirect_stderr(io.StringIO()) as error:
            result = main(["--products", str(self.products.with_name("missing.csv"))])
        self.assertEqual(result, 1)
        self.assertIn("Error:", error.getvalue())


if __name__ == "__main__":
    unittest.main()
