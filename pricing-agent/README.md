# Dynamic Pricing AI Agent

A university prototype for 99x that uses Gemini to recommend product prices
from CSV data. Includes a minimal black-and-white web UI and a CLI.
Governance features will be integrated later.

## First-time setup

Requires Python 3.11+ and a Gemini API key. From the repository root:

```powershell
cd pricing-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Create `.env` inside `pricing-agent/`, beside `pyproject.toml`:

```dotenv
GEMINI_API_KEY=your-key-here
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey).
The app loads `.env` automatically from the agent folder. Keep the key
private; `.env` is ignored by Git. Restart the server after changing the key.
An existing terminal environment variable takes priority over `.env`.

## Run the web UI

Open PowerShell in `pricing-agent/` and run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pricing_agent.web --port 8001
```

Open [http://127.0.0.1:8001](http://127.0.0.1:8001).
Keep PowerShell open; press **Ctrl+C** to stop the server.
Use a different `--port` if that port is already occupied.

Use the chat shortcuts or type:

| Command | Action |
| --- | --- |
| `run agent` | Analyze all products and apply valid price recommendations to CSV. |
| `show changes` | Display the latest run's price changes and reasons. |
| `show current stock` | Display saved prices and available stock. |

The UI also has Overview, Inventory, and Latest run views. Pricing requires
internet access and available Gemini quota. Stock and change queries make no
LLM calls. Chat uses simple command matching; Gemini makes pricing decisions.

Latest-run details reset when the server restarts. Saved prices remain in CSV.
Only runs started through this web server appear in its latest-run view.

Default CSV and `.env` paths resolve from the project folder, independently of
where the terminal was opened. After moving the project or rebuilding `.venv`,
stop older servers and restart using the current environment. If packages or
runtime files are missing, run `python -m pip install -e .` from `pricing-agent/`.

## CLI

From `pricing-agent/`, with the virtual environment active:

```powershell
# Inspect data without API calls or price changes
python -m pricing_agent

# Run AI pricing and save updated prices
python -m pricing_agent --run
```

## Data and workflow

| File | Required columns |
| --- | --- |
| `data/products.csv` | `product_id`, `name`, `cost`, `current_price`, `stock_quantity`, `demand_level` |
| `data/competitors.csv` | `product_id`, `competitor_name`, `price` |

Match competitor records using `product_id`. Use one currency, monetary values
with at most two decimal places, non-negative stock, and demand of `low`,
`medium`, or `high`. The included data is for demonstration.

The agent loads the CSVs, asks Gemini for a price and reason for each product,
validates all recommendations, then saves changed prices. Keeping the current
price is a valid outcome. Stock and demand are supplied observations, not live
market feeds. Avoid simultaneous CLI and web pricing runs against the same file.

## Project structure

```text
pricing-agent/
├── data/                    Product and competitor CSVs
├── src/pricing_agent/       Agent, validation, CSV updater, CLI, and web server
│   └── static/              Web UI HTML, CSS, and JavaScript
├── tests/                   Automated tests
├── .env                     Local API key (ignored by Git)
├── .env.example             API key placeholder
├── .gitignore
├── pyproject.toml           Dependencies and package configuration
└── README.md
```

Both interfaces share the pricing workflow in `service.py`. CSV price changes
pass through `CsvPriceUpdater.apply_updates()` in `price_updater.py`, providing
the integration point for the future governance framework.

## Tests

Run from `pricing-agent/`, with the virtual environment active:

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary CSVs and simulated recommendations, without Gemini API calls.
