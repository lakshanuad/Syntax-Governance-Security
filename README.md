# Dynamic Pricing AI Agent

A standalone Dynamic Pricing AI Agent for Phase 1 of a second-year university
project assigned by 99x. The wider project is an AI Agent Governance & Security
Framework; this phase implements only the pricing agent.

The prototype uses Python, CSV storage, a CLI, a minimal black-and-white local
web UI, and an actual Gemini LLM call. It does not require a database or
e-commerce platform. No governance features are implemented.

## Setup and usage

The agent loads product and competitor data, asks Gemini for structured pricing
recommendations, validates the results, and updates product prices through a
separate CSV updater. Demand and stock come from the CSV, not live market feeds.

Requires Python 3.11 or newer and a Gemini API key for pricing runs.
Pricing also requires internet access and available API quota. Obtain a key from
[Google AI Studio](https://aistudio.google.com/apikey).

Run these commands from the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pricing_agent
```

The editable installation (`-e .`) installs the dependencies declared in
`pyproject.toml` and makes the source package importable while you develop it.
It also installs the equivalent `pricing-agent` command.

The default command only inspects data. To request AI recommendations and update
`data/products.csv`:

```powershell
$env:GEMINI_API_KEY = 'your-key-here'
python -m pricing_agent --run
```

Keep the API key private and out of source files. The model is configured in
`src/pricing_agent/llm_client.py` and is currently `gemini-3.1-flash-lite`.
The environment variable above lasts for the current PowerShell session; set it
again in a new terminal. The application does not load `.env` files automatically.

A pricing run makes one API request per product,
so provider quotas apply. All recommendations must pass validation before the
updater is called. The updater writes a temporary CSV and replaces the original
after writing completes. Run only one updater against a file at a time.

To choose different files:

```powershell
python -m pricing_agent --products data/products.csv --competitors data/competitors.csv
```

Add `--run` to apply AI pricing to the selected product file. Inspection does not
make API requests. Successful commands return 0; handled errors return 1.
Paths are relative to the current working directory.

### Try a run on a copy

```powershell
Copy-Item -LiteralPath data/products.csv -Destination data/products-demo.csv
python -m pricing_agent --run --products data/products-demo.csv
Import-Csv data/products-demo.csv | Select-Object product_id, name, current_price
```

This creates a local demo file and applies recommendations to that copy. The
demo file is not required by the project. Only the selected product CSV is
updated; the competitor CSV is read only.

## Local web UI

Activate the virtual environment and set your key in the same terminal before
starting the server:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:GEMINI_API_KEY = 'your-key-here'
python -m pricing_agent.web
```

Open [the pricing workspace](http://127.0.0.1:8000) in your browser. The equivalent
installed command is `pricing-agent-ui`. Stop the server with Ctrl+C.
No frontend build or extra dependencies are required.

The UI includes:

- **Overview:** product count, total stock, out-of-stock count, inventory, and
  the latest completed run.
- **Inventory:** current saved prices, stock quantities, and supplied demand.
- **Latest run:** before-and-after prices and the agent's reason for each product,
  including unchanged prices.
- **Chat:** type `run agent`, `show changes`, or `show current stock`, or use
  the matching shortcut buttons.

Running the agent from chat immediately requests recommendations and applies
valid prices to the selected CSV. Progress appears while the run is active, and
the inventory refreshes after saving. Only one run can be active in this web
server at a time. Avoid running the CLI against the same CSV simultaneously.

Chat commands use simple intent matching; Gemini makes the pricing decisions.
Reading stock or changes makes no LLM call. Stock inspection works without an
API key. The key remains in the Python server environment and is not sent to
the browser. If you set or change it, restart the server from that terminal.

Latest-run details are held **in memory for the current server session**. They
survive page refreshes, but reset when the server restarts. The UI does not show
earlier CLI runs or keep a persistent change history. Saved prices remain in CSV.

To use a different port or product file:

```powershell
python -m pricing_agent.web --port 8001 --products data/products-demo.csv --competitors data/competitors.csv
```

Create the selected CSV before using it. This server binds to `127.0.0.1` and is
intended for a local university prototype, not public hosting.

## Agent workflow

1. Read and validate product and competitor CSV files.
2. Match competitor records to each product using `product_id`.
3. Prepare the product cost, current price, stock, demand, and competitor prices.
4. Ask Gemini to choose a suitable price and provide a brief explanation.
5. Parse the structured JSON response and validate its product ID, price, and reason.
6. Collect validated recommendations for all products.
7. Pass all validated recommendations to `CsvPriceUpdater.apply_updates()`.
8. Save changed prices and display decisions, reasons, and updated/unchanged counts.

The LLM makes the pricing recommendation rather than explaining a fixed formula.
Python handles input parsing, monetary values, recommendation validation, and
file updates. Recommendations may keep the current price.

The requested response has this structure:

```json
{
  "product_id": "P001",
  "proposed_price": "89.00",
  "reason": "The current price remains within the supplied competitor range."
}
```

Example CLI output (actual recommendations and counts can vary):

```text
Analyzing Wireless Headphones (1/3)
...
Saving validated prices
P001: Wireless Headphones
  Previous: 89.00 | Current: 89.00
  Reason: The current price remains within the supplied competitor range.
...
Completed: 1 prices updated, 2 unchanged.
```

If a handled API, network, or recommendation-validation error occurs during
analysis, the run stops before applying any price updates. A successful web run
also retains its before-and-after values in memory for display.

## Data

`data/products.csv` columns:

```csv
product_id,name,cost,current_price,stock_quantity,demand_level
P001,Wireless Headphones,55.00,89.00,11,high
```

| Column | Meaning |
| --- | --- |
| product_id | Unique, non-empty product identifier |
| name | Product name |
| cost | Non-negative unit cost |
| current_price | Positive selling price |
| stock_quantity | Non-negative count of sellable units |
| demand_level | low, medium, or high |

`data/competitors.csv` columns:

```csv
product_id,competitor_name,price
P001,Demo Shop A,85.00
P001,Demo Shop B,92.00
```

| Column | Meaning |
| --- | --- |
| product_id | Identifier present in products.csv |
| competitor_name | Competitor name, unique per product (case insensitive) |
| price | Positive competitor selling price |

Use one currency consistently across both files. Money is parsed with Python
`Decimal` and must have at most two decimal places. Missing competitor observations
are allowed; a competitor CSV with only the header is valid. At least one product
is required. Files use UTF-8; a UTF-8 BOM is accepted.

The updater preserves existing columns and row order, changing only the
`current_price` values that differ from the recommendations. CSV serialization
may change quoting or line endings. If every recommended price is unchanged,
the updater does not rewrite the file.

The provided data is for demonstration only. Names and selling prices follow
the existing `Inventroy.csv`; costs, demand, and competitor prices are invented.
Stock uses its `available` column, assuming that column already represents
sellable inventory. The original inventory file is untouched and is not loaded
by the CLI or web UI.

## Structure

```text
data/
    products.csv              Product inputs and saved prices
    competitors.csv           Competitor observations
src/pricing_agent/
    __init__.py               Package definition
    __main__.py               python -m pricing_agent entry point
    models.py                 Product, competitor, and recommendation records
    csv_store.py              CSV input validation and loading
    context.py                Product and matching competitor context
    llm_client.py             Gemini API connection
    agent.py                  Pricing prompt and structured recommendation
    recommendation.py         Recommendation validation
    price_updater.py          CSV price updates
    service.py                Shared CLI and UI pricing workflow
    cli.py                    Input display and pricing workflow
    web.py                    Local HTTP server, chat commands, and run status
    static/                   HTML, CSS, and JavaScript for the UI
tests/
    test_csv_store.py          CSV and inspection CLI tests
    test_recommendation.py     Recommendation validation tests
    test_price_updater.py      CSV update tests
    test_web.py                Shared workflow, chat, and HTTP integration tests
Inventroy.csv                 Original inventory reference; not used at runtime
pyproject.toml                Dependencies, package, and CLI configuration
README.md                     Setup and project documentation
```

`CsvPriceUpdater.apply_updates(recommendations)` is the single operation used by
the shared service to write price changes. A future governance framework can replace or
intercept that operation without changing the agent's reasoning.

## Tests

Tests use temporary files and simulated pricing recommendations; they do not
make Gemini API calls. The current suite contains 25 tests covering input
validation, inspection, recommendation validation, CSV updates, the shared pricing
workflow, chat commands, duplicate-run handling, failures, and HTTP endpoints.

```powershell
python -m unittest discover -s tests -v
```

If you have not installed the package with `pip install -e .`, set
`$env:PYTHONPATH = 'src'` before running module commands or tests.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `No module named pricing_agent` | Run `python -m pip install -e .` from the repository root in the active virtual environment. |
| Missing `google.genai` or `httpx` | Install project dependencies with `python -m pip install -e .` using the same Python environment as the CLI. |
| Missing API key | Set `$env:GEMINI_API_KEY` in the terminal used to start the pricing run. |
| API authentication or quota error | Check the key, project access, and available model quota in Google AI Studio. |
| CSV file not found | Run from the repository root or provide explicit file paths. |
| Price-save access error | Check directory permissions and close applications that may lock the product CSV. |
| UI says an API key is needed | Stop the server, set `GEMINI_API_KEY`, and restart it from the same terminal. |
| Port already in use | Choose another port, for example `python -m pricing_agent.web --port 8001`. |
| Latest run is empty after restarting | Run summaries are session-only; saved CSV prices remain available in Inventory. |

## Prototype limitations

- Market conditions are represented by manually supplied demand and stock data;
  there are no live competitor feeds, sales history, or demand forecasts.
- LLM recommendations can vary between runs and are not guaranteed to maximize
  profit. Numeric validation does not establish that a recommendation is good
  business advice or ensure a price is above cost.
- Zero-stock products are still analyzed. There is no automatic scheduling,
  retry strategy, or coordination between separate server/CLI processes.
- The application saves current prices only; the UI keeps the latest completed
  run in memory and does not store recommendation history. Permissions,
  governance policies, approval workflows, audit logging,
  and security dashboards remain outside this phase.
