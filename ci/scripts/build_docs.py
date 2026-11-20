#!/usr/bin/env python3
"""Generate KiCad 10 documentation assets (Schematic PDF/SVG, 2D SVG, 3D PNG, STEP)
and compile a static GitHub Pages site combining manual docs (`docs/*.md`) with
auto-generated hardware artifacts (iBOM, Priced BOM slider, Renders, Reports, Downloads).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import markdown

from config_loader import kicad_env, load_config, resolve_project_path


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"[DOCS] {' '.join(cmd)}")
    res = subprocess.run(cmd, env=kicad_env(), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}")
    return res


def export_kicad_docs(
    cfg: Dict[str, Any], out_dir: Path, prefix: str, skip_3d: bool = False
) -> Dict[str, Any]:
    """Export schematic PDF/SVG, 2D PCB SVGs, 3D raytraced renders, and STEP model."""
    sch_path = resolve_project_path(cfg, "schematic")
    pcb_path = resolve_project_path(cfg, "pcb")

    assets_dir = out_dir / "generated"
    sch_svg_dir = assets_dir / "schematic_svg"
    renders_dir = assets_dir / "renders"
    for d in (assets_dir, sch_svg_dir, renders_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Schematic PDF + SVGs
    sch_pdf = out_dir / f"{prefix}-schematic.pdf"
    _run(["kicad-cli", "sch", "export", "pdf", "--output", str(sch_pdf), str(sch_path)])
    _run(["kicad-cli", "sch", "export", "svg", "--output", str(sch_svg_dir), str(sch_path)])

    # 2. 2D PCB SVGs (Top & Bottom)
    top_svg = renders_dir / "pcb-2d-top.svg"
    bot_svg = renders_dir / "pcb-2d-bottom.svg"
    _run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "svg",
            "--layers",
            "F.Cu,F.Silkscreen,F.Mask,Edge.Cuts",
            "--mode-single",
            "--exclude-drawing-sheet",
            "--page-size-mode",
            "2",
            "--check-zones",
            "--output",
            str(top_svg),
            str(pcb_path),
        ]
    )
    _run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "svg",
            "--layers",
            "B.Cu,B.Silkscreen,B.Mask,Edge.Cuts",
            "--mirror",
            "--mode-single",
            "--exclude-drawing-sheet",
            "--page-size-mode",
            "2",
            "--check-zones",
            "--output",
            str(bot_svg),
            str(pcb_path),
        ]
    )

    # 3. 3D Raytraced PNG renders + STEP model
    r_cfg = cfg.get("renders", {})
    w = str(r_cfg.get("width", 1600))
    h = str(r_cfg.get("height", 1200))
    quality = str(r_cfg.get("quality", "raytrace_post"))
    rendered_3d: List[Tuple[str, Path]] = []

    step_file = out_dir / f"{prefix}-3d.step"
    if not skip_3d:
        for view in r_cfg.get("views", [{"name": "top", "side": "top", "rotate": ""}]):
            vname = view["name"]
            out_png = renders_dir / f"pcb-3d-{vname}.png"
            cmd = [
                "kicad-cli",
                "pcb",
                "render",
                "--side",
                view.get("side", "top"),
                "--width",
                w,
                "--height",
                h,
                "--background",
                "transparent",
                "--quality",
                quality,
                "--perspective",
                "--output",
                str(out_png),
            ]
            if view.get("rotate"):
                cmd.extend(["--rotate", str(view["rotate"])])
            cmd.append(str(pcb_path))
            res = _run(cmd, check=False)
            # Fallback to basic quality if raytrace fails in constrained runner
            if res.returncode != 0 or not out_png.is_file():
                cmd[cmd.index(quality)] = "basic"
                _run(cmd, check=False)
            if out_png.is_file():
                rendered_3d.append((vname, out_png))

        _run(
            [
                "kicad-cli",
                "pcb",
                "export",
                "step",
                "--force",
                "--subst-models",
                "--no-dnp",
                "--output",
                str(step_file),
                str(pcb_path),
            ],
            check=False,
        )

    # Zip all renders for release attachment
    renders_zip = out_dir / f"{prefix}-renders.zip"
    with zipfile.ZipFile(renders_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(renders_dir.iterdir()):
            if f.is_file():
                zf.write(f, arcname=f.name)

    return {
        "sch_pdf": sch_pdf,
        "sch_svgs": sorted(sch_svg_dir.glob("*.svg")),
        "top_svg": top_svg,
        "bot_svg": bot_svg,
        "rendered_3d": rendered_3d,
        "step_file": step_file if step_file.is_file() else None,
        "renders_zip": renders_zip,
    }


def _parse_frontmatter(raw: str) -> Tuple[Dict[str, str], str]:
    """Parse optional YAML-like frontmatter (--- key: value ---) at top of a Markdown file."""
    meta: Dict[str, str] = {}
    if raw.startswith("---\n"):
        end = raw.find("\n---", 4)
        if end != -1:
            block = raw[4:end]
            body = raw[end + 4 :].lstrip("\n")
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            return meta, body
    return meta, raw


def _discover_manual_pages(manual_dir: Path) -> List[Dict[str, Any]]:
    """Discover all user-authored Markdown files in docs/ (excluding README.md)."""
    pages: List[Dict[str, Any]] = []
    if not manual_dir.is_dir():
        return pages

    for md_file in sorted(manual_dir.glob("*.md")):
        if md_file.name.lower() in ("readme.md",):
            continue
        raw = md_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        if meta.get("publish", "true").lower() == "false":
            continue
        slug = "index" if md_file.stem.lower() == "index" else md_file.stem.lower()
        # Infer title from frontmatter -> first H1 -> filename
        title = meta.get("title", "")
        if not title:
            m = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
            title = m.group(1).strip() if m else md_file.stem.replace("-", " ").replace("_", " ").title()
        default_order = 0 if slug == "index" else (90 if slug == "changelog" else 50)
        try:
            order = int(meta.get("order", default_order))
        except ValueError:
            order = default_order
        pages.append(
            {
                "slug": slug,
                "href": f"{slug}.html",
                "title": title,
                "order": order,
                "body_md": body,
            }
        )

    pages.sort(key=lambda p: (p["order"], p["title"].lower()))
    return pages


def _site_shell(
    site_title: str,
    version: str,
    page_title: str,
    active_href: str,
    manual_nav: List[Dict[str, Any]],
    auto_nav: List[Tuple[str, str]],
    content_html: str,
) -> str:
    def _nav_links(items: List[Tuple[str, str]]) -> str:
        out = []
        for label, href in items:
            cls = ' class="active"' if href == active_href else ""
            out.append(f'<a href="{href}"{cls}>{html.escape(label)}</a>')
        return "\n".join(out)

    manual_links = _nav_links([(p["title"], p["href"]) for p in manual_nav])
    auto_links = _nav_links(auto_nav)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(page_title)} — {html.escape(site_title)} ({html.escape(version)})</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --surface-2: #1f2630;
    --border: #30363d; --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6; display: flex; min-height: 100vh;
  }}
  nav {{
    width: 260px; flex-shrink: 0; background: var(--surface);
    border-right: 1px solid var(--border); padding: 20px 16px;
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
  }}
  .brand {{ font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; }}
  .ver {{
    display: inline-block; font-size: 0.78rem; padding: 2px 8px; border-radius: 999px;
    background: rgba(88,166,255,0.14); color: var(--accent); margin-bottom: 18px;
  }}
  .nav-sec {{
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--muted); margin: 16px 0 6px 8px; font-weight: 600;
  }}
  nav a {{
    display: block; padding: 7px 10px; border-radius: 6px; color: var(--text);
    text-decoration: none; font-size: 0.92rem; margin-bottom: 2px;
  }}
  nav a:hover {{ background: var(--surface-2); }}
  nav a.active {{ background: rgba(88,166,255,0.16); color: var(--accent); font-weight: 600; }}
  main {{ flex: 1; padding: 32px 40px; max-width: 1120px; min-width: 0; }}
  h1, h2, h3 {{ border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  h3 {{ border-bottom: none; }}
  a {{ color: var(--accent); }}
  img {{ max-width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--border); }}
  pre {{ background: var(--surface); border: 1px solid var(--border); padding: 14px; border-radius: 8px; overflow-x: auto; }}
  code {{ background: var(--surface-2); padding: 2px 5px; border-radius: 4px; font-size: 0.88em; }}
  pre code {{ background: none; padding: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; }}
  th {{ background: var(--surface-2); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin: 16px 0; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .card img {{ background: #10141a; display: block; margin: 0 auto; }}
  .card .cap {{ color: var(--muted); font-size: 0.85rem; margin-top: 8px; text-align: center; }}
  .btn {{
    display: inline-block; background: #238636; color: #fff !important; text-decoration: none;
    padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; margin: 4px 6px 4px 0;
  }}
  .btn.sec {{ background: var(--surface-2); border: 1px solid var(--border); color: var(--text) !important; }}
  .alert-banner {{
    background: rgba(248, 81, 73, 0.14);
    border: 2px solid #f85149;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 22px;
    color: #ffdcd7;
  }}
  .alert-banner strong {{ color: #ff7b72; }}
  .alert-banner a {{ color: #ff9a93; font-weight: 600; }}
  .svg-box {{ background: #fff; border-radius: 8px; padding: 10px; margin-bottom: 18px; border: 1px solid var(--border); }}
  .svg-box img {{ border: none; }}
  @media (max-width: 820px) {{
    body {{ flex-direction: column; }}
    nav {{ width: 100%; height: auto; position: static; border-right: none; border-bottom: 1px solid var(--border); }}
    main {{ padding: 20px; }}
  }}
</style>
</head>
<body>
  <nav>
    <div class="brand">{html.escape(site_title)}</div>
    <div class="ver">{html.escape(version)}</div>
    <div class="nav-sec">Documentation</div>
    {manual_links}
    <div class="nav-sec">Hardware Artifacts</div>
    {auto_links}
  </nav>
  <main>
    {content_html}
  </main>
</body>
</html>
"""


def build_site(
    cfg: Dict[str, Any],
    site_dir: Path,
    docs_assets: Dict[str, Any],
    version: str,
    ibom_path: Optional[Path] = None,
    bom_html_path: Optional[Path] = None,
    checks_md_path: Optional[Path] = None,
    checks_json_path: Optional[Path] = None,
    download_files: Optional[List[Tuple[str, Path]]] = None,
) -> None:
    root = Path(cfg["_root"])
    manual_dir = root / cfg.get("docs", {}).get("manual_dir", "docs")
    site_title = cfg["project"].get("display_name", cfg["project"]["name"])

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    files_dir = site_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    img_dir = site_dir / "renders"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Copy user-managed static assets from docs/assets or docs/images
    for sub in ("assets", "images", "img"):
        src = manual_dir / sub
        if src.is_dir():
            shutil.copytree(src, site_dir / sub, dirs_exist_ok=True)

    # Copy generated renders & schematic SVGs into site
    copied_3d: List[Tuple[str, str]] = []
    for name, p in docs_assets.get("rendered_3d", []):
        if p and p.is_file():
            dst = img_dir / p.name
            shutil.copy2(p, dst)
            copied_3d.append((name, f"renders/{p.name}"))

    copied_2d: List[Tuple[str, str]] = []
    for label, key in (("2D Top View", "top_svg"), ("2D Bottom View", "bot_svg")):
        p = docs_assets.get(key)
        if p and p.is_file():
            dst = img_dir / p.name
            shutil.copy2(p, dst)
            copied_2d.append((label, f"renders/{p.name}"))

    copied_sch_svgs: List[Tuple[str, str]] = []
    for svg in docs_assets.get("sch_svgs", []):
        dst = img_dir / f"sch-{svg.name}"
        shutil.copy2(svg, dst)
        copied_sch_svgs.append((svg.stem, f"renders/{dst.name}"))

    # Copy downloadable files
    dl_entries: List[Tuple[str, str, str]] = []
    for label, src in download_files or []:
        if src and src.is_file():
            dst = files_dir / src.name
            shutil.copy2(src, dst)
            size_kb = max(1, src.stat().st_size // 1024)
            dl_entries.append((label, f"files/{src.name}", f"{size_kb:,} KB"))

    # Copy iBOM and Priced BOM HTML
    has_ibom = False
    if ibom_path and ibom_path.is_file():
        shutil.copy2(ibom_path, site_dir / "ibom.html")
        has_ibom = True

    has_bom_calc = False
    if bom_html_path and bom_html_path.is_file():
        shutil.copy2(bom_html_path, site_dir / "bom.html")
        has_bom_calc = True

    manual_pages = _discover_manual_pages(manual_dir)
    if not any(p["slug"] == "index" for p in manual_pages):
        manual_pages.insert(
            0,
            {
                "slug": "index",
                "href": "index.html",
                "title": "Overview",
                "order": 0,
                "body_md": f"# {site_title}\n\nAdd your own documentation in `docs/index.md`.",
            },
        )

    # Build a prominent error banner if ERC or DRC errors > 0
    error_banner_html = ""
    checks_nav_label = "ERC & DRC Reports"
    if checks_json_path and checks_json_path.is_file():
        chk_data = json.loads(checks_json_path.read_text(encoding="utf-8"))
        erc_e = int(chk_data.get("erc", {}).get("errors", 0))
        drc_e = int(chk_data.get("drc", {}).get("errors", 0))
        if erc_e > 0 or drc_e > 0:
            checks_nav_label = f"🚨 ERC & DRC ({erc_e + drc_e} err)"
            error_banner_html = (
                '<div class="alert-banner">'
                f"<strong>🚨 CAUTION — {erc_e + drc_e} KiCad ERROR(S) DETECTED "
                f"({erc_e} ERC, {drc_e} DRC)</strong><br>"
                'This build completed without blocking. Review the <a href="checks.html">ERC &amp; DRC Report</a> '
                "before manufacturing or ordering PCBs."
                "</div>\n"
            )

    auto_nav: List[Tuple[str, str]] = [
        ("PCB Renders & 3D", "renders.html"),
        ("Schematic", "schematic.html"),
    ]
    if has_bom_calc:
        auto_nav.append(("Priced BOM & Stock", "bom.html"))
    if has_ibom:
        auto_nav.append(("Interactive BOM (iBOM)", "ibom.html"))
    auto_nav.append((checks_nav_label, "checks.html"))
    auto_nav.append(("Manufacturing Downloads", "downloads.html"))

    md_conv = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])

    # 1. Render all manual Markdown pages
    for page in manual_pages:
        md_conv.reset()
        body_html = md_conv.convert(page["body_md"])
        # On the index page, show error banner (if any) + quick hero preview
        if page["slug"] == "index":
            body_html = error_banner_html + body_html
        if page["slug"] == "index" and copied_3d:
            hero = ['<h2>Board Preview</h2><div class="grid">']
            for name, rel in copied_3d[:2]:
                hero.append(
                    f'<div class="card"><img src="{rel}" alt="{html.escape(name)}">'
                    f'<div class="cap">{html.escape(name.title())}</div></div>'
                )
            hero.append("</div><p>")
            if has_bom_calc:
                hero.append('<a class="btn" href="bom.html">Open Priced BOM Calculator</a>')
            if has_ibom:
                hero.append('<a class="btn sec" href="ibom.html">Open Interactive BOM (iBOM)</a>')
            hero.append('<a class="btn sec" href="downloads.html">Download JLCPCB Files</a></p>')
            body_html += "\n".join(hero)

        out_html = _site_shell(
            site_title, version, page["title"], page["href"], manual_pages, auto_nav, body_html
        )
        (site_dir / page["href"]).write_text(out_html, encoding="utf-8")

    # 2. Renders & 3D page
    r_html = ["<h1>PCB Renders &amp; 3D Model</h1>"]
    step_dl = next((href for lbl, href, _ in dl_entries if "STEP" in lbl), None)
    if step_dl:
        r_html.append(f'<p><a class="btn" href="{step_dl}">Download 3D STEP Model</a></p>')
    if copied_3d:
        r_html.append('<h2>3D Renders</h2><div class="grid">')
        for name, rel in copied_3d:
            r_html.append(
                f'<div class="card"><img src="{rel}" alt="{html.escape(name)}">'
                f'<div class="cap">{html.escape(name.replace("-", " ").title())}</div></div>'
            )
        r_html.append("</div>")
    if copied_2d:
        r_html.append('<h2>2D Copper &amp; Silkscreen</h2><div class="grid">')
        for label, rel in copied_2d:
            r_html.append(
                f'<div class="card"><img src="{rel}" alt="{html.escape(label)}">'
                f'<div class="cap">{html.escape(label)}</div></div>'
            )
        r_html.append("</div>")
    (site_dir / "renders.html").write_text(
        _site_shell(site_title, version, "PCB Renders & 3D", "renders.html", manual_pages, auto_nav, "\n".join(r_html)),
        encoding="utf-8",
    )

    # 3. Schematic page
    s_html = ["<h1>Schematic</h1>"]
    pdf_dl = next((href for lbl, href, _ in dl_entries if "Schematic PDF" in lbl), None)
    if pdf_dl:
        s_html.append(f'<p><a class="btn" href="{pdf_dl}">Download Schematic PDF</a></p>')
    for title, rel in copied_sch_svgs:
        s_html.append(f'<h3>{html.escape(title)}</h3><div class="svg-box"><img src="{rel}" alt="{html.escape(title)}"></div>')
    (site_dir / "schematic.html").write_text(
        _site_shell(site_title, version, "Schematic", "schematic.html", manual_pages, auto_nav, "\n".join(s_html)),
        encoding="utf-8",
    )

    # 4. Checks page
    if checks_md_path and checks_md_path.is_file():
        md_conv.reset()
        checks_html = error_banner_html + md_conv.convert(checks_md_path.read_text(encoding="utf-8"))
    else:
        checks_html = error_banner_html + "<h1>ERC &amp; DRC Reports</h1><p>No check report was attached to this build.</p>"
    (site_dir / "checks.html").write_text(
        _site_shell(site_title, version, "ERC & DRC Reports", "checks.html", manual_pages, auto_nav, checks_html),
        encoding="utf-8",
    )

    # 5. Downloads page
    d_html = [
        error_banner_html,
        "<h1>Manufacturing &amp; Design Downloads</h1>",
        "<table><thead><tr><th>Artifact</th><th>Size</th><th>Download</th></tr></thead><tbody>",
    ]
    for label, href, size in dl_entries:
        d_html.append(
            f'<tr><td>{html.escape(label)}</td><td>{size}</td>'
            f'<td><a class="btn sec" href="{href}">Download</a></td></tr>'
        )
    d_html.append("</tbody></table>")
    (site_dir / "downloads.html").write_text(
        _site_shell(site_title, version, "Downloads", "downloads.html", manual_pages, auto_nav, "\n".join(d_html)),
        encoding="utf-8",
    )

    # Prevent GitHub Pages Jekyll processing
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    print(f"[DOCS] Built static site at {site_dir} ({len(manual_pages)} manual page(s)).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Export KiCad docs and build static GitHub Pages site.")
    ap.add_argument("--out-dir", required=True, help="Output directory for generated docs & site")
    ap.add_argument("--version", default="dev", help="Release tag or SHA")
    ap.add_argument("--config", default=None, help="Path to ci/config.yml")
    ap.add_argument("--jlcpcb-dir", default=None, help="Directory with JLCPCB outputs")
    ap.add_argument("--ibom", default=None, help="Path to generated ibom.html")
    ap.add_argument("--bom-html", default=None, help="Path to generated priced bom.html")
    ap.add_argument("--bom-csv", default=None, help="Path to generated bom-priced.csv")
    ap.add_argument("--checks-md", default=None, help="Path to checks-summary.md")
    ap.add_argument("--checks-json", default=None, help="Path to checks-summary.json")
    ap.add_argument("--skip-3d", action="store_true", help="Skip 3D renders and STEP export")
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{cfg['project']['name']}-{args.version}"

    docs_assets = export_kicad_docs(cfg, out_dir, prefix, skip_3d=args.skip_3d)

    downloads: List[Tuple[str, Path]] = []
    if args.jlcpcb_dir:
        jdir = Path(args.jlcpcb_dir)
        for pattern, label in (
            ("*-jlcpcb-production.zip", "JLCPCB Full PCBA Bundle (ZIP)"),
            ("*-jlcpcb-gerbers.zip", "JLCPCB Gerbers + Drills (ZIP)"),
            ("*-jlcpcb-bom.csv", "JLCPCB BOM (CSV)"),
            ("*-jlcpcb-cpl.csv", "JLCPCB Pick & Place CPL (CSV)"),
        ):
            for f in sorted(jdir.glob(pattern)):
                downloads.append((label, f))
    if args.bom_csv and Path(args.bom_csv).is_file():
        downloads.append(("Priced BOM Snapshot (CSV)", Path(args.bom_csv)))
    downloads.append(("Schematic PDF", docs_assets["sch_pdf"]))
    if docs_assets.get("step_file"):
        downloads.append(("3D Mechanical Model (STEP)", docs_assets["step_file"]))
    downloads.append(("PCB Renders Pack (ZIP)", docs_assets["renders_zip"]))

    build_site(
        cfg=cfg,
        site_dir=out_dir / "site",
        docs_assets=docs_assets,
        version=args.version,
        ibom_path=Path(args.ibom) if args.ibom else None,
        bom_html_path=Path(args.bom_html) if args.bom_html else None,
        checks_md_path=Path(args.checks_md) if args.checks_md else None,
        checks_json_path=Path(args.checks_json) if args.checks_json else None,
        download_files=downloads,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
