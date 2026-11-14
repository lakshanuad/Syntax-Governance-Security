"""Local-only web UI. Run with: python -m pricing_agent.web."""
from dotenv import load_dotenv
import argparse
from copy import deepcopy
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from threading import Lock, Thread
from urllib.parse import urlsplit

from .service import PricingService

ASSETS = Path(__file__).parent / "static"


class WebApp:
    """In-memory status of this UI session; no persistent run history."""

    def __init__(self, service: PricingService):
        self.service = service
        self.lock = Lock()
        self.running = False
        self.progress = "Ready when you are"
        self.last_run = None
        self.error = None
        self.attempt = 0

    def snapshot(self) -> dict:
        with self.lock:
            status = deepcopy({
                "running": self.running,
                "progress": self.progress,
                "last_run": self.last_run,
                "error": self.error,
                "attempt": self.attempt,
            })
        status["products"] = self.service.inventory()
        status["api_key_ready"] = bool(os.environ.get("GEMINI_API_KEY"))
        return status

    def start_run(self) -> str:
        with self.lock:
            if self.running:
                return "The agent is already running. You can follow its progress here."
            if not os.environ.get("GEMINI_API_KEY"):
                return "Set GEMINI_API_KEY in the terminal, then restart the web app to run pricing. Stock and latest-run views work without a key."
            self.running = True
            self.progress = "Preparing product and competitor data"
            self.error = None
            self.attempt += 1
        Thread(target=self._run, daemon=True).start()
        return "Starting the pricing agent. I’ll compare each product with its competitors and apply valid price recommendations."

    def _run(self):
        try:
            result = self.service.run(self._progress)
        except Exception as error:
            # Keep the server available after provider, input, or file errors.
            # Do not expose SDK response bodies or credentials to the browser.
            from google.genai import errors

            if isinstance(error, errors.APIError):
                message = f"Gemini request failed (HTTP {error.code}). Check your API access or quota in Google AI Studio."
            elif isinstance(error, (ValueError, OSError)):
                message = str(error)
            else:
                message = "Pricing could not finish. Check your connection and input files, then try again."
            with self.lock:
                self.error = message
                self.progress = "Run failed"
                self.running = False
        else:
            with self.lock:
                self.last_run = result
                self.progress = "Pricing complete"
                self.running = False

    def _progress(self, message: str):
        with self.lock:
            self.progress = message

    def chat(self, message: str) -> dict:
        words = set(re.findall(r"[a-z]+", message.lower()))
        if words & {"stock", "inventory", "units", "products"}:
            products = self.service.inventory()
            lines = [f"{p['name']}: {p['stock_quantity']} units · price {p['current_price']}" for p in products]
            return {"action": "stock", "message": "Here’s the current stock:\n\n" + "\n".join(lines)}
        if words & {"changes", "changed", "change", "latest", "last", "history"}:
            with self.lock:
                result = deepcopy(self.last_run)
            if result is None:
                reply = "No completed pricing run in this session yet. Run the agent to see price changes and the reasoning behind them."
            else:
                changes = [d for d in result["decisions"] if d["changed"]]
                reply = f"Latest run: {result['changed']} updated, {result['unchanged']} unchanged."
                for change in changes:
                    reply += f"\n\n{change['name']}: {change['old_price']} → {change['new_price']}\n{change['reason']}"
                if not changes:
                    reply += "\nThe agent kept all current prices. See Latest run for each explanation."
            return {"action": "changes", "message": reply}
        command = message.strip().lower()
        run_pattern = (
            r"(?:(?:please|can you|could you)\s+)?"
            r"(?:run|start|execute|reprice)"
            r"(?:\s+(?:the\s+)?(?:pricing\s+)?(?:agent|analysis|prices|pricing))?"
            r"(?:\s+(?:now|please))?[.!?]*"
        )
        if re.fullmatch(run_pattern, command):
            return {"action": "run", "message": self.start_run()}
        return {"action": "help", "message": "I can run the pricing agent, show current stock, or explain the latest price changes. Try ‘run agent’, ‘show stock’, or ‘show changes’."}


def make_server(app: WebApp, port: int = 8000) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, data: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, value: dict, status: int = 200):
            self.send_body(json.dumps(value).encode(), "application/json; charset=utf-8", status)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/state":
                try:
                    self.send_json(app.snapshot())
                except (ValueError, OSError) as error:
                    self.send_json({"error": str(error)}, 400)
                return
            assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.css": ("app.css", "text/css; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            }
            if path not in assets:
                self.send_json({"error": "Not found"}, 404)
                return
            filename, content_type = assets[path]
            self.send_body((ASSETS / filename).read_bytes(), content_type)

        def do_POST(self):
            if urlsplit(self.path).path != "/api/chat":
                self.send_json({"error": "Not found"}, 404)
                return
            # Accept only JSON requests from this local page, without enabling CORS.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.send_json({"error": "Expected JSON"}, 415)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise ValueError("Message is too long or empty")
                body = json.loads(self.rfile.read(size))
                message = body.get("message") if isinstance(body, dict) else None
                if not isinstance(message, str) or not message.strip():
                    raise ValueError("Enter a message")
                result = app.chat(message.strip())
            except (ValueError, OSError) as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json(result)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path.cwd() / ".env")
    parser = argparse.ArgumentParser(description="Open the local dynamic pricing workspace.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--products", type=Path, default=Path("data/products.csv"))
    parser.add_argument("--competitors", type=Path, default=Path("data/competitors.csv"))
    args = parser.parse_args(argv)
    app = WebApp(PricingService(args.products, args.competitors))
    try:
        app.service.inventory()
        server = make_server(app, args.port)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Cannot start UI: {error}\n")
    print(f"Pricing workspace: http://127.0.0.1:{server.server_port}", flush=True)
    print("Press Ctrl+C to stop. Latest-run details are kept for this session only.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
