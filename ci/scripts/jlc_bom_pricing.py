#!/usr/bin/env python3
"""Fetch live JLCPCB / LCSC pricing & availability and generate:
- bom-priced.json  (structured data + price tiers + summary at 1/5/10/50/100 boards)
- <prefix>-bom-priced.csv
- bom.html         (interactive BOM cost & stock explorer with board-count slider)
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config_loader import load_config

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) KiCad-CI-BOM/1.0"


def _http_get_json(url: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _parse_jlcsearch_tiers(comp: Dict[str, Any]) -> List[Dict[str, Any]]:
    tiers: List[Dict[str, Any]] = []
    extra = comp.get("extra")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = None
    if isinstance(extra, dict):
        prices = extra.get("prices") or extra.get("price") or []
        if isinstance(prices, list):
            for p in prices:
                if not isinstance(p, dict):
                    continue
                q = p.get("qFrom") or p.get("min_qty") or p.get("qty") or 1
                pr = p.get("price") or p.get("usdPrice")
                if pr is not None:
                    try:
                        tiers.append({"min_qty": int(q), "unit_price": float(pr)})
                    except (TypeError, ValueError):
                        pass
    if not tiers:
        p1 = comp.get("price1") or comp.get("price")
        if p1 is not None:
            try:
                tiers.append({"min_qty": 1, "unit_price": float(p1)})
            except (TypeError, ValueError):
                pass
    tiers.sort(key=lambda t: t["min_qty"])
    return tiers


def fetch_part_data(lcsc_code: str, offline: bool = False) -> Dict[str, Any]:
    """Fetch JLCPCB SMT + LCSC tiered pricing data for a single LCSC part code."""
    code = lcsc_code.strip().upper()
    result: Dict[str, Any] = {
        "lcsc": code,
        "found": False,
        "source": [],
        "mfr": "",
        "brand": "",
        "description": "",
        "library_type": "Unknown",  # Basic | Preferred | Extended | Unknown
        "jlc_stock": None,
        "lcsc_stock": None,
        "stock": None,
        "price_tiers": [],
        "datasheet_url": "",
        "lcsc_url": f"https://www.lcsc.com/product-detail/{code}.html",
        "jlc_url": f"https://jlcpcb.com/partdetail/{code}",
    }
    if offline or not code:
        return result

    num_code = code[1:] if code.startswith("C") else code

    # 1) Query jlcsearch (fast JLCPCB SMT catalog mirror: Basic/Extended + JLC SMT stock)
    jlc_url = (
        "https://jlcsearch.tscircuit.com/components/list.json?"
        + urllib.parse.urlencode({"search": code, "full": "true", "limit": "10"})
    )
    jlc_json = _http_get_json(jlc_url, timeout=10.0)
    if isinstance(jlc_json, dict):
        comps = jlc_json.get("components") or []
        matched = None
        for c in comps:
            c_lcsc = str(c.get("lcsc", "")).strip().upper()
            if c_lcsc == code or c_lcsc == num_code:
                matched = c
                break
        if matched:
            result["found"] = True
            result["source"].append("jlcsearch")
            result["mfr"] = str(matched.get("mfr") or "")
            result["description"] = str(matched.get("description") or "")
            if matched.get("stock") is not None:
                try:
                    result["jlc_stock"] = int(matched["stock"])
                except (TypeError, ValueError):
                    pass
            is_basic = bool(matched.get("is_basic") or matched.get("basic"))
            is_pref = bool(matched.get("is_preferred") or matched.get("preferred"))
            if is_basic:
                result["library_type"] = "Basic"
            elif is_pref:
                result["library_type"] = "Preferred"
            else:
                result["library_type"] = "Extended"
            jlc_tiers = _parse_jlcsearch_tiers(matched)
            if jlc_tiers:
                result["price_tiers"] = jlc_tiers

    # 2) Query LCSC product detail API for full volume price breaks & real-time stock
    lcsc_api = (
        "https://wmsc.lcsc.com/ftps/wm/product/detail?"
        + urllib.parse.urlencode({"productCode": code})
    )
    lcsc_json = _http_get_json(lcsc_api, timeout=10.0)
    prod = (lcsc_json or {}).get("result") if isinstance(lcsc_json, dict) else None
    if isinstance(prod, dict) and prod.get("productCode"):
        result["found"] = True
        result["source"].append("lcsc")
        if not result["mfr"]:
            result["mfr"] = str(prod.get("productModel") or "")
        result["brand"] = str(prod.get("brandNameEn") or "")
        if not result["description"]:
            result["description"] = str(
                prod.get("productIntroEn") or prod.get("productDescEn") or ""
            )
        if prod.get("pdfUrl"):
            result["datasheet_url"] = str(prod["pdfUrl"])
        if prod.get("stockNumber") is not None:
            try:
                result["lcsc_stock"] = int(prod["stockNumber"])
            except (TypeError, ValueError):
                pass
        # Full tiered pricing from LCSC
        tiers: List[Dict[str, Any]] = []
        for row in prod.get("productPriceList") or []:
            if not isinstance(row, dict):
                continue
            ladder = row.get("ladder")
            usd = row.get("usdPrice") or row.get("productPrice")
            if ladder is not None and usd is not None:
                try:
                    tiers.append({"min_qty": int(ladder), "unit_price": float(usd)})
                except (TypeError, ValueError):
                    pass
        if tiers:
            tiers.sort(key=lambda t: t["min_qty"])
            result["price_tiers"] = tiers

    # Prefer JLC SMT stock when available, else LCSC warehouse stock
    if result["jlc_stock"] is not None:
        result["stock"] = result["jlc_stock"]
    elif result["lcsc_stock"] is not None:
        result["stock"] = result["lcsc_stock"]

    return result


def unit_price_for_qty(tiers: List[Dict[str, Any]], total_qty: int) -> Optional[float]:
    if not tiers:
        return None
    chosen = tiers[0]["unit_price"]
    for t in tiers:
        if total_qty >= t["min_qty"]:
            chosen = t["unit_price"]
        else:
            break
    return chosen


def compute_board_summary(
    items: List[Dict[str, Any]], board_count: int, extended_fee: float
) -> Dict[str, Any]:
    parts_total = 0.0
    extended_codes = set()
    in_stock_lines = 0
    insufficient_lines = 0
    missing_lcsc_lines = 0
    unpriced_lines = 0

    for it in items:
        needed = it["quantity"] * board_count
        lcsc = it.get("lcsc") or ""
        if not lcsc:
            missing_lcsc_lines += 1
            unpriced_lines += 1
            continue
        if it.get("library_type") not in ("Basic", "Preferred"):
            extended_codes.add(lcsc)
        stock = it.get("stock")
        if stock is None:
            insufficient_lines += 1
        elif stock >= needed:
            in_stock_lines += 1
        else:
            insufficient_lines += 1

        up = unit_price_for_qty(it.get("price_tiers") or [], needed)
        if up is None:
            unpriced_lines += 1
        else:
            parts_total += up * needed

    extended_count = len(extended_codes)
    feeder_fees = extended_count * extended_fee
    grand_total = parts_total + feeder_fees
    return {
        "boards": board_count,
        "parts_total_usd": round(parts_total, 4),
        "parts_per_board_usd": round(parts_total / board_count, 4),
        "extended_parts_count": extended_count,
        "feeder_fees_usd": round(feeder_fees, 2),
        "grand_total_usd": round(grand_total, 4),
        "grand_per_board_usd": round(grand_total / board_count, 4),
        "in_stock_lines": in_stock_lines,
        "insufficient_lines": insufficient_lines,
        "missing_lcsc_lines": missing_lcsc_lines,
        "unpriced_lines": unpriced_lines,
    }


def render_bom_html(payload: Dict[str, Any], embedded: bool = False) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    # Safely escape </script> inside inline JSON
    data_json = data_json.replace("</", "<\\/")
    project_title = payload.get("display_name") or payload.get("project") or "PCB"
    version = payload.get("version") or "dev"
    fetched_at = payload.get("fetched_at") or ""

    back_link = (
        '<a class="back-link" href="index.html">← Back to Docs</a>'
        if embedded
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{project_title} ({version}) — Priced BOM &amp; Availability</title>
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-2: #1f2630;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }}
  .wrap {{ max-width: 1320px; margin: 0 auto; }}
  header {{
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end;
    gap: 12px; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 14px;
  }}
  h1 {{ margin: 0; font-size: 1.55rem; }}
  .meta {{ color: var(--muted); font-size: 0.88rem; }}
  .back-link {{
    color: var(--accent); text-decoration: none; font-size: 0.9rem; display: inline-block; margin-bottom: 6px;
  }}
  .back-link:hover {{ text-decoration: underline; }}

  .control-panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 18px;
  }}
  .slider-row {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 16px;
  }}
  .slider-label {{ font-weight: 600; min-width: 140px; }}
  .slider-wrap {{ flex: 1; min-width: 220px; display: flex; align-items: center; gap: 12px; }}
  input[type="range"] {{
    flex: 1; accent-color: var(--accent); height: 6px; cursor: pointer;
  }}
  input[type="number"] {{
    width: 88px; padding: 6px 10px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
    font-size: 1rem; font-weight: 600; text-align: center;
  }}
  .presets {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; align-items: center; }}
  .presets button {{
    background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.84rem;
  }}
  .presets button:hover, .presets button.active {{
    border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.12);
  }}
  .toggle-fee {{
    margin-left: auto; display: inline-flex; align-items: center; gap: 8px;
    font-size: 0.88rem; color: var(--muted); cursor: pointer;
  }}

  .kpis {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px; margin-bottom: 18px;
  }}
  .kpi {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px;
  }}
  .kpi-label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi-val {{ font-size: 1.55rem; font-weight: 700; margin-top: 4px; }}
  .kpi-sub {{ font-size: 0.8rem; color: var(--muted); margin-top: 2px; }}

  .toolbar {{
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px;
  }}
  .search {{
    flex: 1; min-width: 220px; padding: 8px 12px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--surface); color: var(--text); font-size: 0.92rem;
  }}
  .pill {{
    background: var(--surface); color: var(--muted); border: 1px solid var(--border);
    border-radius: 999px; padding: 5px 12px; font-size: 0.84rem; cursor: pointer;
  }}
  .pill.active {{ border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.12); }}
  .btn-export {{
    background: #238636; color: #fff; border: none; border-radius: 6px;
    padding: 7px 14px; font-weight: 600; cursor: pointer; font-size: 0.86rem;
  }}
  .btn-export:hover {{ background: #2ea043; }}

  .table-wrap {{
    overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; background: var(--surface);
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
  th {{
    background: var(--surface-2); color: var(--muted); font-weight: 600;
    position: sticky; top: 0; cursor: pointer; user-select: none; white-space: nowrap;
  }}
  th:hover {{ color: var(--text); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255,255,255,0.025); }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .refs {{ max-width: 210px; word-break: break-word; font-family: ui-monospace, monospace; font-size: 0.82rem; }}
  .fp {{ color: var(--muted); font-size: 0.82rem; max-width: 220px; word-break: break-word; }}
  a.lcsc {{ color: var(--accent); text-decoration: none; font-family: ui-monospace, monospace; font-weight: 600; }}
  a.lcsc:hover {{ text-decoration: underline; }}

  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; white-space: nowrap;
  }}
  .b-basic {{ background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid rgba(63,185,80,0.35); }}
  .b-pref {{ background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid rgba(88,166,255,0.35); }}
  .b-ext {{ background: rgba(188,140,255,0.14); color: var(--purple); border: 1px solid rgba(188,140,255,0.35); }}
  .b-ok {{ background: rgba(63,185,80,0.15); color: var(--green); }}
  .b-warn {{ background: rgba(210,153,34,0.18); color: var(--yellow); }}
  .b-bad {{ background: rgba(248,81,73,0.18); color: var(--red); }}
  .b-muted {{ background: rgba(139,148,158,0.15); color: var(--muted); }}
  .tiers-hint {{ font-size: 0.74rem; color: var(--muted); display: block; margin-top: 2px; }}
  footer {{ margin-top: 16px; color: var(--muted); font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="wrap">
  {back_link}
  <header>
    <div>
      <h1>{project_title} — JLCPCB Priced BOM &amp; Availability</h1>
      <div class="meta">Version: <strong>{version}</strong> · Prices &amp; stock snapshot fetched: <strong>{fetched_at}</strong></div>
    </div>
    <div class="meta">Pricing uses JLCPCB / LCSC volume breaks · Does not include bare PCB fabrication or shipping</div>
  </header>

  <section class="control-panel">
    <div class="slider-row">
      <div class="slider-label">Board / Assembly Count</div>
      <div class="slider-wrap">
        <input id="boardSlider" type="range" min="1" max="500" step="1" value="5">
        <input id="boardInput" type="number" min="1" max="10000" step="1" value="5">
        <span class="meta">boards</span>
      </div>
    </div>
    <div class="presets">
      <span class="meta">Quick qty:</span>
      <button type="button" data-q="1">1</button>
      <button type="button" data-q="2">2</button>
      <button type="button" data-q="5" class="active">5</button>
      <button type="button" data-q="10">10</button>
      <button type="button" data-q="25">25</button>
      <button type="button" data-q="50">50</button>
      <button type="button" data-q="100">100</button>
      <button type="button" data-q="250">250</button>
      <button type="button" data-q="500">500</button>
      <label class="toggle-fee">
        <input id="includeFeeder" type="checkbox" checked>
        Include JLCPCB Extended feeder fee ($<span id="feeVal">3.00</span> / unique extended part)
      </label>
    </div>
  </section>

  <section class="kpis">
    <div class="kpi">
      <div class="kpi-label">Components / Board</div>
      <div class="kpi-val" id="kpiPartsPerBoard">$0.00</div>
      <div class="kpi-sub" id="kpiPartsTotal">Total: $0.00</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Extended Feeder Fees</div>
      <div class="kpi-val" id="kpiFees">$0.00</div>
      <div class="kpi-sub" id="kpiExtCount">0 extended parts</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Est. Total (Parts + Fees)</div>
      <div class="kpi-val" id="kpiGrandTotal" style="color:var(--accent)">$0.00</div>
      <div class="kpi-sub" id="kpiGrandPerBoard">$0.00 / board</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Stock Availability</div>
      <div class="kpi-val" id="kpiStockHealth">—</div>
      <div class="kpi-sub" id="kpiStockSub">—</div>
    </div>
  </section>

  <section class="toolbar">
    <input id="searchBox" class="search" type="search" placeholder="Filter by designator, value, footprint, MPN, or LCSC code...">
    <button class="pill active" data-filter="all">All</button>
    <button class="pill" data-filter="basic">Basic / Pref</button>
    <button class="pill" data-filter="extended">Extended</button>
    <button class="pill" data-filter="issue">Stock / Missing Issues</button>
    <button id="exportCsv" class="btn-export" type="button">Download CSV (<span id="exportQty">5</span> boards)</button>
  </section>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-sort="designator_str">Designators</th>
          <th data-sort="comment">Value / MPN</th>
          <th data-sort="footprint">Footprint</th>
          <th data-sort="lcsc">LCSC Part #</th>
          <th data-sort="library_type">JLC Type</th>
          <th data-sort="stock" class="num">Stock</th>
          <th data-sort="quantity" class="num">Qty / Bd</th>
          <th data-sort="total_qty" class="num">Total Qty</th>
          <th data-sort="unit_price" class="num">Unit Price</th>
          <th data-sort="line_total" class="num">Line Total</th>
        </tr>
      </thead>
      <tbody id="bomBody"></tbody>
    </table>
  </div>

  <footer>
    Total placements per board: <strong id="footPlacements">0</strong> · Unique BOM lines: <strong id="footLines">0</strong> · Click any column header to sort.
  </footer>
</div>

<script>
const BOM_DATA = {data_json};

let boardCount = 5;
let includeFeeder = true;
let activeFilter = "all";
let searchTerm = "";
let sortKey = "designator_str";
let sortAsc = true;

const slider = document.getElementById("boardSlider");
const numInput = document.getElementById("boardInput");
const feeCheckbox = document.getElementById("includeFeeder");
const feeUnit = Number(BOM_DATA.extended_part_fee_usd ?? 3.0);
document.getElementById("feeVal").textContent = feeUnit.toFixed(2);
document.getElementById("footPlacements").textContent = BOM_DATA.total_components;
document.getElementById("footLines").textContent = BOM_DATA.unique_parts;

function fmtUsd(v, digits = 2) {{
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return "$" + v.toFixed(digits);
}}

function fmtUnit(v) {{
  if (v === null || v === undefined) return "—";
  if (v < 0.01) return "$" + v.toFixed(5);
  if (v < 1) return "$" + v.toFixed(4);
  return "$" + v.toFixed(3);
}}

function getTierPrice(tiers, totalQty) {{
  if (!tiers || !tiers.length) return null;
  let chosen = tiers[0].unit_price;
  for (const t of tiers) {{
    if (totalQty >= t.min_qty) chosen = t.unit_price;
    else break;
  }}
  return chosen;
}}

function computeRows() {{
  return BOM_DATA.items.map(it => {{
    const totalQty = it.quantity * boardCount;
    const unitPrice = getTierPrice(it.price_tiers, totalQty);
    const lineTotal = unitPrice !== null ? unitPrice * totalQty : null;
    const hasLcsc = Boolean(it.lcsc);
    const stock = it.stock;
    let status = "ok";
    if (!hasLcsc) status = "missing";
    else if (stock === null || stock === undefined) status = "unknown";
    else if (stock === 0) status = "out";
    else if (stock < totalQty) status = "short";
    else if (stock < totalQty * 3) status = "low";
    return {{ ...it, total_qty: totalQty, unit_price: unitPrice, line_total: lineTotal, status }};
  }});
}}

function render() {{
  const rows = computeRows();

  let partsTotal = 0;
  const extCodes = new Set();
  let okLines = 0;
  let issueLines = 0;
  let missingLines = 0;

  for (const r of rows) {{
    if (r.line_total !== null) partsTotal += r.line_total;
    if (r.lcsc && r.library_type !== "Basic" && r.library_type !== "Preferred") extCodes.add(r.lcsc);
    if (r.status === "ok" || r.status === "low") okLines++;
    else {{
      issueLines++;
      if (r.status === "missing") missingLines++;
    }}
  }}

  const extCount = extCodes.size;
  const fees = includeFeeder ? extCount * feeUnit : 0;
  const grand = partsTotal + fees;

  document.getElementById("kpiPartsPerBoard").textContent = fmtUsd(partsTotal / boardCount);
  document.getElementById("kpiPartsTotal").textContent = `Total (${{boardCount}} boards): ${{fmtUsd(partsTotal)}}`;
  document.getElementById("kpiFees").textContent = fmtUsd(fees);
  document.getElementById("kpiExtCount").textContent = `${{extCount}} extended part${{extCount === 1 ? "" : "s"}}`;
  document.getElementById("kpiGrandTotal").textContent = fmtUsd(grand);
  document.getElementById("kpiGrandPerBoard").textContent = `${{fmtUsd(grand / boardCount)}} / board`;
  document.getElementById("exportQty").textContent = boardCount;

  const stockEl = document.getElementById("kpiStockHealth");
  stockEl.textContent = `${{okLines}} / ${{rows.length}} ready`;
  stockEl.style.color = issueLines === 0 ? "var(--green)" : (missingLines > 0 ? "var(--yellow)" : "var(--red)");
  document.getElementById("kpiStockSub").textContent =
    issueLines === 0
      ? `All parts in stock for ${{boardCount}} boards`
      : `${{issueLines}} line${{issueLines === 1 ? "" : "s"}} need attention (${{missingLines}} missing LCSC)`;

  // Filter
  const q = searchTerm.trim().toLowerCase();
  let filtered = rows.filter(r => {{
    if (activeFilter === "basic" && r.library_type !== "Basic" && r.library_type !== "Preferred") return false;
    if (activeFilter === "extended" && (!r.lcsc || r.library_type === "Basic" || r.library_type === "Preferred")) return false;
    if (activeFilter === "issue" && (r.status === "ok")) return false;
    if (!q) return true;
    const hay = `${{r.designator_str}} ${{r.comment}} ${{r.footprint}} ${{r.lcsc}} ${{r.mfr || ""}} ${{r.description || ""}}`.toLowerCase();
    return hay.includes(q);
  }});

  // Sort
  filtered.sort((a, b) => {{
    let va = a[sortKey], vb = b[sortKey];
    if (va === null || va === undefined) va = sortAsc ? Infinity : -Infinity;
    if (vb === null || vb === undefined) vb = sortAsc ? Infinity : -Infinity;
    if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va;
    return sortAsc ? String(va).localeCompare(String(vb), undefined, {{ numeric: true }})
                   : String(vb).localeCompare(String(va), undefined, {{ numeric: true }});
  }});

  const tbody = document.getElementById("bomBody");
  tbody.innerHTML = filtered.map(r => {{
    let libBadge = '<span class="badge b-muted">—</span>';
    if (r.lcsc) {{
      if (r.library_type === "Basic") libBadge = '<span class="badge b-basic">Basic</span>';
      else if (r.library_type === "Preferred") libBadge = '<span class="badge b-pref">Preferred</span>';
      else libBadge = '<span class="badge b-ext">Extended</span>';
    }}

    let stockHtml = "";
    if (r.status === "missing") stockHtml = '<span class="badge b-warn">No LCSC</span>';
    else if (r.status === "unknown") stockHtml = '<span class="badge b-muted">Unknown</span>';
    else if (r.status === "out") stockHtml = '<span class="badge b-bad">Out of Stock</span>';
    else if (r.status === "short") stockHtml = `<span class="badge b-bad">${{r.stock.toLocaleString()}} (need ${{r.total_qty}})</span>`;
    else if (r.status === "low") stockHtml = `<span class="badge b-warn">${{r.stock.toLocaleString()}} (low)</span>`;
    else stockHtml = `<span class="badge b-ok">${{r.stock.toLocaleString()}}</span>`;

    const lcscHtml = r.lcsc
      ? `<a class="lcsc" href="${{r.lcsc_url}}" target="_blank" rel="noopener">${{r.lcsc}}</a>`
      : '<span class="badge b-warn">Missing</span>';

    const mfrSub = r.mfr ? `<div class="tiers-hint">${{r.mfr}}</div>` : "";
    const tierHint = (r.price_tiers && r.price_tiers.length > 1)
      ? `<span class="tiers-hint">${{r.price_tiers.slice(0, 3).map(t => `${{t.min_qty}}+: ${{fmtUnit(t.unit_price)}}`).join(" · ")}}</span>`
      : "";

    return `<tr>
      <td class="refs">${{r.designator_str}}</td>
      <td><strong>${{r.comment}}</strong>${{mfrSub}}</td>
      <td class="fp">${{r.footprint}}</td>
      <td>${{lcscHtml}}</td>
      <td>${{libBadge}}</td>
      <td class="num">${{stockHtml}}</td>
      <td class="num">${{r.quantity}}</td>
      <td class="num"><strong>${{r.total_qty}}</strong></td>
      <td class="num">${{fmtUnit(r.unit_price)}}${{tierHint}}</td>
      <td class="num"><strong>${{fmtUsd(r.line_total, 3)}}</strong></td>
    </tr>`;
  }}).join("");
}}

function setBoards(val) {{
  const n = Math.max(1, Math.min(10000, parseInt(val, 10) || 1));
  boardCount = n;
  slider.value = Math.min(500, n);
  numInput.value = n;
  document.querySelectorAll(".presets button[data-q]").forEach(b => {{
    b.classList.toggle("active", Number(b.dataset.q) === n);
  }});
  render();
}}

slider.addEventListener("input", e => setBoards(e.target.value));
numInput.addEventListener("input", e => setBoards(e.target.value));
feeCheckbox.addEventListener("change", e => {{ includeFeeder = e.target.checked; render(); }});
document.getElementById("searchBox").addEventListener("input", e => {{ searchTerm = e.target.value; render(); }});

document.querySelectorAll(".presets button[data-q]").forEach(btn => {{
  btn.addEventListener("click", () => setBoards(btn.dataset.q));
}});
document.querySelectorAll(".pill").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.filter;
    render();
  }});
}});
document.querySelectorAll("th[data-sort]").forEach(th => {{
  th.addEventListener("click", () => {{
    const k = th.dataset.sort;
    if (sortKey === k) sortAsc = !sortAsc;
    else {{ sortKey = k; sortAsc = true; }}
    render();
  }});
}});

document.getElementById("exportCsv").addEventListener("click", () => {{
  const rows = computeRows();
  const header = ["Designators", "Value", "Footprint", "LCSC Part #", "JLC Type", "Stock", "Qty/Board", `Total Qty (${{boardCount}} bd)`, "Unit Price (USD)", "Line Total (USD)"];
  const esc = v => `"${{String(v ?? "").replace(/"/g, '""')}}"`;
  const lines = [header.map(esc).join(",")];
  for (const r of rows) {{
    lines.push([
      r.designator_str, r.comment, r.footprint, r.lcsc, r.library_type,
      r.stock ?? "", r.quantity, r.total_qty,
      r.unit_price !== null ? r.unit_price.toFixed(5) : "",
      r.line_total !== null ? r.line_total.toFixed(4) : ""
    ].map(esc).join(","));
  }}
  const blob = new Blob([lines.join("\\n")], {{ type: "text/csv;charset=utf-8;" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${{BOM_DATA.project}}-${{BOM_DATA.version}}-bom-${{boardCount}}pcs.csv`;
  a.click();
}});

render();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch JLC/LCSC pricing & generate interactive BOM.")
    ap.add_argument("--bom-json", required=True, help="Input bom-merged.json from build_jlcpcb.py")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--version", default="dev", help="Release version or SHA")
    ap.add_argument("--config", default=None, help="Path to ci/config.yml")
    ap.add_argument("--offline", action="store_true", help="Skip HTTP calls (offline dry-run)")
    ap.add_argument("--embedded", action="store_true", help="Include back-to-docs link in bom.html")
    args = ap.parse_args()

    cfg = load_config(args.config)
    bom_data = json.loads(Path(args.bom_json).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    unique_lcsc = sorted({it["lcsc"] for it in bom_data["items"] if it.get("lcsc")})
    print(f"[BOM-PRICE] Querying {len(unique_lcsc)} unique LCSC parts (offline={args.offline})...")

    fetched: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(fetch_part_data, code, args.offline): code for code in unique_lcsc}
        for fut in as_completed(futs):
            code = futs[fut]
            try:
                fetched[code] = fut.result()
            except Exception as exc:
                print(f"[BOM-PRICE] Warning: failed {code}: {exc}")
                fetched[code] = fetch_part_data(code, offline=True)

    enriched_items: List[Dict[str, Any]] = []
    for it in bom_data["items"]:
        code = it.get("lcsc") or ""
        info = fetched.get(code, {})
        merged = dict(it)
        merged.update(
            {
                "found": info.get("found", False),
                "mfr": info.get("mfr", ""),
                "brand": info.get("brand", ""),
                "description": info.get("description", ""),
                "library_type": info.get("library_type", "Unknown") if code else "Missing",
                "jlc_stock": info.get("jlc_stock"),
                "lcsc_stock": info.get("lcsc_stock"),
                "stock": info.get("stock"),
                "price_tiers": info.get("price_tiers", []),
                "datasheet_url": info.get("datasheet_url") or it.get("datasheet", ""),
                "lcsc_url": info.get("lcsc_url", ""),
                "jlc_url": info.get("jlc_url", ""),
            }
        )
        enriched_items.append(merged)

    ext_fee = float(cfg["jlcpcb"].get("extended_part_fee_usd", 3.0))
    summaries = {
        str(q): compute_board_summary(enriched_items, q, ext_fee)
        for q in (1, 5, 10, 50, 100)
    }

    payload = {
        "project": cfg["project"]["name"],
        "display_name": cfg["project"].get("display_name", cfg["project"]["name"]),
        "board": cfg["project"]["board_name"],
        "version": args.version,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "extended_part_fee_usd": ext_fee,
        "total_components": bom_data["total_components"],
        "unique_parts": bom_data["unique_parts"],
        "missing_lcsc_groups": bom_data["missing_lcsc_groups"],
        "summaries": summaries,
        "items": enriched_items,
    }

    priced_json = out_dir / "bom-priced.json"
    priced_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Write static priced CSV
    prefix = f"{cfg['project']['name']}-{args.version}"
    priced_csv = out_dir / f"{prefix}-bom-priced.csv"
    with priced_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Designators",
                "Value",
                "Footprint",
                "Qty/Board",
                "LCSC Part #",
                "JLC Type",
                "Stock",
                "Unit @1bd (USD)",
                "Unit @5bd (USD)",
                "Unit @10bd (USD)",
                "Unit @50bd (USD)",
                "MPN",
            ]
        )
        for it in enriched_items:
            tiers = it["price_tiers"]
            q = it["quantity"]
            p1 = unit_price_for_qty(tiers, q * 1)
            p5 = unit_price_for_qty(tiers, q * 5)
            p10 = unit_price_for_qty(tiers, q * 10)
            p50 = unit_price_for_qty(tiers, q * 50)
            w.writerow(
                [
                    it["designator_str"],
                    it["comment"],
                    it["footprint"],
                    q,
                    it["lcsc"],
                    it["library_type"],
                    "" if it["stock"] is None else it["stock"],
                    "" if p1 is None else f"{p1:.5f}",
                    "" if p5 is None else f"{p5:.5f}",
                    "" if p10 is None else f"{p10:.5f}",
                    "" if p50 is None else f"{p50:.5f}",
                    it["mfr"],
                ]
            )

    bom_html = out_dir / "bom.html"
    bom_html.write_text(render_bom_html(payload, embedded=args.embedded), encoding="utf-8")

    s5 = summaries["5"]
    print(
        f"[BOM-PRICE] Done. @5 boards: parts=${s5['parts_total_usd']:.2f} "
        f"(${s5['parts_per_board_usd']:.2f}/bd) + ${s5['feeder_fees_usd']:.2f} feeder fees "
        f"({s5['in_stock_lines']}/{len(enriched_items)} lines in stock)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
