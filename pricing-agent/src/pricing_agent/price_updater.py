import csv
import os
import tempfile
from pathlib import Path

from .csv_store import load_products
from .models import PriceRecommendation
from .recommendation import validate_recommendation


class CsvPriceUpdater:
    def __init__(self, products_path: Path):
        self.products_path = products_path

    def apply_updates(
        self,
        recommendations: list[PriceRecommendation],
    ) -> int:
        products = load_products(self.products_path)
        products_by_id = {
            product.product_id: product
            for product in products
        }

        updates = {}

        for recommendation in recommendations:
            product_id = recommendation.product_id

            if product_id not in products_by_id:
                raise ValueError(f"Unknown product: {product_id}")

            if product_id in updates:
                raise ValueError(f"Duplicate update: {product_id}")

            checked = validate_recommendation(
                {
                    "product_id": product_id,
                    "proposed_price": str(
                        recommendation.proposed_price
                    ),
                    "reason": recommendation.reason,
                },
                products_by_id[product_id],
            )

            updates[product_id] = checked.proposed_price

        with self.products_path.open(
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            rows = list(reader)

        changed_count = 0

        for row in rows:
            product_id = row["product_id"].strip()

            if product_id not in updates:
                continue

            new_price = updates[product_id]
            old_price = products_by_id[product_id].current_price

            if new_price != old_price:
                row["current_price"] = f"{new_price:.2f}"
                changed_count += 1

        if changed_count == 0:
            return 0

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self.products_path.parent,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)

                writer = csv.DictWriter(
                    handle,
                    fieldnames=fieldnames,
                )
                writer.writeheader()
                writer.writerows(rows)

            os.replace(temporary_path, self.products_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return changed_count