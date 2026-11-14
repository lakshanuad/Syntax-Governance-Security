import json
from contextlib import chdir
import os
from decimal import Decimal
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pricing_agent.models import PriceRecommendation
from pricing_agent.service import PricingService
from pricing_agent.web import WebApp, make_server


class WebTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.products = Path(self.directory.name) / "products.csv"
        self.competitors = Path(self.directory.name) / "competitors.csv"
        self.products.write_text(
            "product_id,name,cost,current_price,stock_quantity,demand_level\n"
            "P001,Mouse,10.00,20.00,5,high\n"
            "P002,Keyboard,20.00,35.00,0,low\n", encoding="utf-8")
        self.competitors.write_text(
            "product_id,competitor_name,price\nP001,Demo Shop,22.00\n", encoding="utf-8")
        self.service = PricingService(self.products, self.competitors, self.propose)
        self.app = WebApp(self.service)

    @staticmethod
    def propose(product, competitors):
        price = Decimal("21.00") if product.product_id == "P001" else product.current_price
        return PriceRecommendation(product.product_id, price, "Simulated recommendation for testing.")

    def test_run_saves_prices_and_returns_before_after_and_reasons(self):
        progress = []
        result = self.service.run(progress.append)
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(result["decisions"][0]["old_price"], "20.00")
        self.assertEqual(result["decisions"][0]["new_price"], "21.00")
        self.assertTrue(result["decisions"][0]["reason"])
        self.assertEqual(self.service.inventory()[0]["current_price"], "21.00")
        self.assertEqual(progress[-1], "Saving validated prices")

    def test_relative_input_paths_remain_valid_after_working_directory_changes(self):
        with chdir(self.directory.name):
            service = PricingService(Path("products.csv"), Path("competitors.csv"), self.propose)
        result = service.run()
        self.assertEqual(result["changed"], 1)
        self.assertTrue(service.products_path.is_absolute())

    def test_missing_runtime_file_has_actionable_error(self):
        self.service.run = lambda progress: (_ for _ in ()).throw(FileNotFoundError(2, "No such file or directory"))
        self.app._run()
        self.assertIn("Reinstall dependencies", self.app.error)
        self.assertFalse(self.app.running)

    def test_failure_on_later_product_does_not_apply_earlier_recommendation(self):
        before = self.products.read_bytes()

        def fail_on_second(product, competitors):
            if product.product_id == "P002":
                raise ValueError("Invalid recommendation")
            return self.propose(product, competitors)

        self.service.proposer = fail_on_second
        with self.assertRaises(ValueError):
            self.service.run()
        self.assertEqual(self.products.read_bytes(), before)

    def test_wrong_product_recommendation_is_rejected_before_write(self):
        before = self.products.read_bytes()
        self.service.proposer = lambda p, c: PriceRecommendation("P999", Decimal("21.00"), "Wrong product")
        with self.assertRaises(ValueError):
            self.service.run()
        self.assertEqual(self.products.read_bytes(), before)

    def test_stock_chat_does_not_call_agent_and_preserves_stock(self):
        self.service.proposer = lambda p, c: self.fail("Stock must not call the LLM")
        reply = self.app.chat("show current stock")
        self.assertEqual(reply["action"], "stock")
        self.assertIn("Keyboard: 0 units", reply["message"])
        self.assertEqual(self.app.snapshot()["products"][0]["stock_quantity"], 5)

    def test_missing_key_does_not_start_a_run(self):
        with patch.dict(os.environ, {}, clear=True):
            reply = self.app.chat("run agent")
        self.assertIn("GEMINI_API_KEY", reply["message"])
        self.assertFalse(self.app.running)

    def test_questions_and_negation_do_not_start_runs(self):
        with patch.object(self.app, "start_run") as start:
            for message in ("Do not run the agent", "How do I run the agent?", "Don't start pricing"):
                self.assertEqual(self.app.chat(message)["action"], "help")
            start.assert_not_called()

    def test_duplicate_run_is_not_started(self):
        started, finish = Event(), Event()
        original_run = self.service.run

        def blocking_run(progress):
            started.set()
            finish.wait(5)
            return original_run(progress)

        self.service.run = blocking_run
        try:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-not-a-real-key"}):
                self.app.start_run()
                self.assertTrue(started.wait(2))
                self.assertIn("already running", self.app.start_run())
        finally:
            finish.set()
        self.wait_for_run()
        self.assertEqual(self.app.last_run["changed"], 1)

    def wait_for_run(self):
        import time
        deadline = time.monotonic() + 5
        while self.app.running and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.app.running)

    def test_failed_run_resets_status_and_retains_previous_completed_result(self):
        self.app.last_run = self.service.run()
        previous = self.app.last_run["id"]
        self.service.proposer = lambda p, c: (_ for _ in ()).throw(ValueError("Test failure"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-not-a-real-key"}):
            self.app.start_run()
            self.wait_for_run()
        self.assertEqual(self.app.error, "Test failure")
        self.assertEqual(self.app.last_run["id"], previous)

    def test_changes_reflect_only_successful_run_in_current_session(self):
        self.assertIn("No completed", self.app.chat("show changes")["message"])
        self.app.last_run = self.service.run()
        reply = self.app.chat("what changes has done")
        self.assertIn("20.00 → 21.00", reply["message"])
        self.assertIn("1 updated, 1 unchanged", reply["message"])
        self.assertIsNone(WebApp(self.service).last_run)

    def test_http_page_state_chat_and_invalid_requests(self):
        server = make_server(self.app, 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/", timeout=5) as response:
                self.assertIn(b"Pricing assistant", response.read())
            for asset in ("/app.css", "/app.js"):
                with urlopen(base + asset, timeout=5) as response:
                    self.assertEqual(response.status, 200)
            with urlopen(base + "/api/state", timeout=5) as response:
                data = json.load(response)
                self.assertEqual(len(data["products"]), 2)
                self.assertNotIn("api_key", data)
            request = Request(base + "/api/chat", json.dumps({"message": "show stock"}).encode(), {"Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                self.assertEqual(json.load(response)["action"], "stock")
            invalid = Request(base + "/api/chat", b'{"message":42}', {"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(invalid, timeout=5)
            self.assertEqual(error.exception.code, 400)
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/../pyproject.toml", timeout=5)
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
