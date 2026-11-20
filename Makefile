PYTHON ?= python3
VERSION ?= local
OUT_DIR ?= build
OFFLINE ?=

.PHONY: help check check-nofail jlcpcb bom-price docs ibom all clean

help:
	@echo "KiCad 10 Local CI Targets:"
	@echo "  make check          - Run ERC & DRC (fail on errors, show warnings)"
	@echo "  make check-nofail   - Run ERC & DRC in report-only mode"
	@echo "  make jlcpcb         - Generate JLCPCB Gerbers, merged BOM & CPL"
	@echo "  make bom-price      - Fetch JLC/LCSC pricing & generate interactive bom.html"
	@echo "  make ibom           - Generate InteractiveHtmlBom (requires InteractiveHtmlBom installed)"
	@echo "  make docs           - Export Schematic PDF, 2D/3D renders, STEP & build Pages site"
	@echo "  make all            - Run full local release pipeline into $(OUT_DIR)/"
	@echo "  make clean          - Remove $(OUT_DIR)/"

check:
	$(PYTHON) ci/scripts/parse_checks.py --out-dir $(OUT_DIR)/reports

check-nofail:
	$(PYTHON) ci/scripts/parse_checks.py --out-dir $(OUT_DIR)/reports --no-fail

jlcpcb:
	$(PYTHON) ci/scripts/build_jlcpcb.py --out-dir $(OUT_DIR)/jlcpcb --version $(VERSION)

bom-price: jlcpcb
	$(PYTHON) ci/scripts/jlc_bom_pricing.py \
		--bom-json $(OUT_DIR)/jlcpcb/bom-merged.json \
		--out-dir $(OUT_DIR)/bom \
		--version $(VERSION) \
		--embedded $(if $(OFFLINE),--offline,)

ibom:
	mkdir -p $(OUT_DIR)/ibom
	INTERACTIVE_HTML_BOM_NO_DISPLAY=1 generate_interactive_bom \
		--no-browser --dark-mode \
		--extra-fields "LCSC Part,LCSC Part #" \
		--dest-dir $(OUT_DIR)/ibom \
		--name-format "ibom" \
		handspinner_pcb.kicad_pcb

docs: jlcpcb bom-price
	$(PYTHON) ci/scripts/build_docs.py \
		--out-dir $(OUT_DIR)/docs \
		--version $(VERSION) \
		--jlcpcb-dir $(OUT_DIR)/jlcpcb \
		--bom-html $(OUT_DIR)/bom/bom.html \
		--bom-csv $(OUT_DIR)/bom/e-spin-$(VERSION)-bom-priced.csv \
		$(if $(wildcard $(OUT_DIR)/ibom/ibom.html),--ibom $(OUT_DIR)/ibom/ibom.html,) \
		$(if $(wildcard $(OUT_DIR)/reports/checks-summary.md),--checks-md $(OUT_DIR)/reports/checks-summary.md,) \
		$(if $(wildcard $(OUT_DIR)/reports/checks-summary.json),--checks-json $(OUT_DIR)/reports/checks-summary.json,)

all: check jlcpcb bom-price docs

clean:
	rm -rf $(OUT_DIR)
