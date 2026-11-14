const $ = (id) => document.getElementById(id);
let state = null;
let currentView = "overview";
let sending = false;
let seenRun = null;
let seenFailure = null;
let initialized = false;
let polling = false;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${name}`);
  svg.append(use);
  svg.setAttribute("aria-hidden", "true");
  return svg;
}

function addMessage(text, role = "assistant") {
  const message = node("div", `message ${role}`);
  message.append(node("div", "message-author", role === "user" ? "YOU" : "PRICING ASSISTANT"));
  message.append(node("div", "", text));
  $("chat-log").append(message);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
}

function setView(view) {
  currentView = view;
  const titles = {
    overview: ["Overview", "Pricing, in focus.", "A little intelligence behind every price."],
    inventory: ["Inventory", "Your stock, clearly.", "Every product. Every price. All in one place."],
    changes: ["Latest run", "Behind every change.", "See what the agent decided, and why."],
  };
  $("breadcrumb").textContent = titles[view][0];
  $("page-title").textContent = titles[view][1];
  $("page-subtitle").textContent = titles[view][2];
  $("inventory-panel").hidden = view === "changes";
  $("run-panel").hidden = view === "inventory";
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

function renderInventory(products) {
  $("product-count").textContent = products.length;
  $("nav-count").textContent = products.length;
  $("stock-count").textContent = products.reduce((sum, p) => sum + p.stock_quantity, 0);
  $("empty-count").textContent = products.filter((p) => p.stock_quantity === 0).length;
  $("inventory-caption").textContent = `${products.length} products · Current saved prices`;
  const rows = products.map((p) => {
    const row = node("tr");
    const product = node("td");
    const cell = node("div", "product-cell");
    const symbol = node("span", "product-symbol");
    symbol.append(icon("box"));
    const name = node("div");
    name.append(node("div", "product-name", p.name), node("div", "product-id", p.product_id));
    cell.append(symbol, name);
    product.append(cell);
    const stock = node("td", `numeric${p.stock_quantity === 0 ? " stock-zero" : ""}`, p.stock_quantity);
    if (p.stock_quantity === 0) stock.append(node("span", "stock-label", "Out of stock"));
    const demand = node("td");
    demand.append(node("span", `demand ${p.demand_level}`, p.demand_level));
    row.append(product, node("td", "numeric", p.current_price), stock, demand);
    return row;
  });
  $("inventory-body").replaceChildren(...rows);
}

function renderRun(result) {
  $("run-empty").hidden = !!result;
  $("run-decisions").hidden = !result;
  if (!result) return;
  $("run-subtitle").textContent = `${result.changed} updated · ${result.unchanged} unchanged`;
  $("run-time").textContent = new Date(result.completed_at).toLocaleString([], {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"});
  $("run-decisions").replaceChildren(...result.decisions.map((d) => {
    const item = node("article", "decision");
    const heading = node("div", "decision-heading");
    const title = node("div", "", d.name);
    title.append(node("span", "kept", d.changed ? "Price updated" : "Price kept"));
    const prices = node("div", "decision-price");
    prices.append(document.createTextNode(d.old_price), node("span", "", "→"), document.createTextNode(d.new_price));
    heading.append(title, prices);
    item.append(heading, node("p", "", d.reason));
    return item;
  }));
}

async function refresh() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/state");
    const next = await response.json();
    if (!response.ok) throw new Error(next.error || "Could not load the workspace.");
    state = next;
    $("connection-error").hidden = !next.error;
    $("connection-error").textContent = next.error || "";
    renderInventory(next.products);
    renderRun(next.last_run);
    $("agent-status").textContent = next.running ? "Working on your prices" : next.api_key_ready ? "Ready to help" : "API key needed to run";
    $("run-progress").hidden = !next.running;
    $("progress-text").textContent = next.progress;
    $("run-badge").textContent = next.running ? "ANALYZING" : next.error ? "RUN FAILED" : next.last_run ? "COMPLETED" : "NOT RUN YET";
    document.querySelectorAll('[data-command="Run agent"]').forEach((button) => {button.disabled = next.running || sending;});
    if (initialized && next.last_run && seenRun !== next.last_run.id) {
      addMessage(`All done. ${next.last_run.changed} prices updated and ${next.last_run.unchanged} unchanged. Your saved prices are now shown in inventory. Open Latest run to see each decision.`);
    }
    if (initialized && next.error && seenFailure !== next.attempt) {
      addMessage(`The run couldn’t finish: ${next.error}`);
    }
    seenRun = next.last_run?.id || null;
    seenFailure = next.error ? next.attempt : null;
    initialized = true;
  } catch (error) {
    $("connection-error").hidden = false;
    $("connection-error").textContent = `Workspace unavailable. ${error.message} Check that the local Python server is running, then refresh.`;
    $("agent-status").textContent = "Connection unavailable";
  } finally {polling = false;}
}

async function sendCommand(message) {
  if (sending || !message.trim()) return;
  sending = true;
  addMessage(message, "user");
  $("chat-input").value = "";
  document.querySelectorAll(".send-button, [data-command]").forEach((button) => {button.disabled = true;});
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Message failed.");
    addMessage(result.message);
    if (result.action === "stock") setView("inventory");
    if (result.action === "changes") setView("changes");
    if (result.action === "run") setView("overview");
  } catch (error) {
    addMessage(`I couldn’t send that request. ${error.message}`);
  } finally {
    sending = false;
    document.querySelectorAll(".send-button, [data-command]").forEach((button) => {button.disabled = false;});
    await refresh();
    $("chat-input").focus({preventScroll: true});
  }
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-command]").forEach((button) => button.addEventListener("click", () => sendCommand(button.dataset.command)));
$("chat-form").addEventListener("submit", (event) => {event.preventDefault(); sendCommand($("chat-input").value.trim());});
$("refresh-button").addEventListener("click", refresh);
setView(currentView);
refresh();
setInterval(() => {if (!document.hidden) refresh();}, 2000);
