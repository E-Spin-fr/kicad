## KiCad 10 ERC & DRC Report — `handspinner_pcb`

> [!CAUTION]
> **🚨 57 KiCad ERROR(S) DETECTED (8 ERC, 49 DRC)** — The pipeline continued without blocking so artifacts remain available. **Do not manufacture before reviewing!**

- **KiCad Version:** `10.0.8`
- **Gate Policy:** Non-blocking — errors are highlighted via alerts & GitHub annotations without stopping the build.

| Check | Status | Errors | Warnings | Exclusions |
| :--- | :---: | :---: | :---: | :---: |
| **ERC** (`handspinner_pcb.kicad_sch`) | 🚨 **8 ERROR(S)** | **8** | 265 | 0 |
| **DRC** (`handspinner_pcb.kicad_pcb`) | 🚨 **49 ERROR(S)** | **49** | 264 | 0 |
| ↳ PCB Rules | — | 47 | 258 | — |
| ↳ Unconnected Items | — | 2 | 0 | — |
| ↳ Schematic Parity | — | 0 | 6 | — |

<details><summary>❌ ERC Errors by Category</summary>

- `power_pin_not_driven`: **4**
- `pin_not_connected`: **3**
- `duplicate_pins`: **1**

1. **`pin_not_connected`** [/]: Pin not connected (Symbol U14 Pin 4 [INT1, Unspecified, Line] @ (21.59, 88.90 mm))
2. **`duplicate_pins`** [/]: Pin  on symbol 'U1' is connected to different nets: GND and VBUS (Symbol U1 Pin  [GND, Power output, Line] @ (33.02, 30.48 mm) — Symbol U1 Pin  [VBUS, Power input, Line] @ (33.02, 33.02 mm))
3. **`power_pin_not_driven`** [/]: Input Power pin not driven by any Output Power pins (Symbol #PWR09 Pin 1 [Power input, Line] @ (163.83, 36.83 mm))
4. **`power_pin_not_driven`** [/]: Input Power pin not driven by any Output Power pins (Symbol #PWR024 Pin 1 [Power input, Line] @ (166.37, 74.93 mm))
5. **`power_pin_not_driven`** [/]: Input Power pin not driven by any Output Power pins (Symbol #PWR05 Pin 1 [Power input, Line] @ (205.74, 39.37 mm))
6. **`pin_not_connected`** [/]: Pin not connected (Symbol U16 Pin 12 [TXD, Unspecified, Line] @ (250.19, 54.61 mm))
7. **`pin_not_connected`** [/]: Pin not connected (Symbol U16 Pin 11 [RXD, Unspecified, Line] @ (250.19, 57.15 mm))
8. **`power_pin_not_driven`** [/]: Input Power pin not driven by any Output Power pins (Symbol #PWR06 Pin 1 [Power input, Line] @ (280.67, 39.37 mm))

</details>

<details><summary>⚠️ ERC Warnings</summary>

- `lib_symbol_issues`: **123**
- `pin_to_pin`: **94**
- `footprint_link_issues`: **44**
- `four_way_junction`: **2**
- `lib_symbol_mismatch`: **2**

1. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR056 [+3.3V] @ (16.51, 91.44 mm))
2. **`footprint_link_issues`** [/]: The current configuration does not include the footprint library 'Capacitor_SMD' (Symbol C22 [C_Small] @ (16.51, 96.52 mm))
3. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'Device' (Symbol C22 [C_Small] @ (16.51, 96.52 mm))
4. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR058 [GND] @ (16.51, 99.06 mm))
5. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR017 [GND] @ (20.32, 57.15 mm))
6. **`pin_to_pin`** [/]: Pins of type Unspecified and Power input are connected (Symbol U14 Pin 5 [VDDIO, Unspecified, Line] @ (21.59, 91.44 mm) — Symbol #PWR056 Pin 1 [Power input, Line] @ (16.51, 91.44 mm))
7. **`pin_to_pin`** [/]: Pins of type Unspecified and Unspecified are connected (Symbol U14 Pin 6 [GND, Unspecified, Line] @ (21.59, 93.98 mm) — Symbol U14 Pin 7 [GND, Unspecified, Line] @ (21.59, 96.52 mm))
8. **`pin_to_pin`** [/]: Pins of type Unspecified and Power input are connected (Symbol U14 Pin 7 [GND, Unspecified, Line] @ (21.59, 96.52 mm) — Symbol #PWR051 Pin 1 [Power input, Line] @ (21.59, 99.06 mm))
9. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR051 [GND] @ (21.59, 99.06 mm))
10. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR038 [VDD] @ (22.86, 143.51 mm))
11. **`pin_to_pin`** [/]: Pins of type Unspecified and Power input are connected (Symbol SW3 Pin 1 [1, Unspecified, Line] @ (22.86, 143.51 mm) — Symbol #PWR038 Pin 1 [Power input, Line] @ (22.86, 143.51 mm))
12. **`lib_symbol_issues`** [/]: The current configuration does not include the symbol library 'power' (Symbol #PWR035 [+BATT] @ (22.86, 148.59 mm))
13. **`pin_to_pin`** [/]: Pins of type Unspecified and Power input are connected (Symbol SW3 Pin 2 [2, Unspecified, Line] @ (22.86, 148.59 mm) — Symbol #PWR035 Pin 1 [Power input, Line] @ (22.86, 148.59 mm))
14. **`pin_to_pin`** [/]: Pins of type Unspecified and Unspecified are connected (Symbol SW3 Pin 6 [6, Unspecified, Line] @ (22.86, 156.21 mm) — Symbol SW3 Pin 7 [7, Unspecified, Line] @ (22.86, 158.75 mm))
15. **`pin_to_pin`** [/]: Pins of type Unspecified and Power input are connected (Symbol SW3 Pin 7 [7, Unspecified, Line] @ (22.86, 158.75 mm) — Symbol #PWR059 Pin 1 [Power input, Line] @ (22.86, 163.83 mm))

_...and 250 more (see full JSON report artifact)._

</details>

<details><summary>❌ DRC Errors by Category</summary>

- `starved_thermal`: **18**
- `courtyards_overlap`: **9**
- `annular_width`: **8**
- `hole_clearance`: **6**
- `clearance`: **4**
- `copper_edge_clearance`: **2**
- `unconnected_items`: **2**

1. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW2 @ (83.85, 117.10 mm))
2. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW2 @ (83.85, 118.90 mm))
3. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW3 @ (127.00, 117.24 mm))
4. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW3 @ (130.00, 117.24 mm))
5. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of U1 @ (155.97, 107.87 mm))
6. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of U1 @ (155.97, 102.08 mm))
7. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW1 @ (83.85, 92.85 mm))
8. **`annular_width`**: Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0000 mm) (PTH pad [<no net>] of SW1 @ (83.85, 91.05 mm))
9. **`clearance`**: Clearance violation ( clearance 0.2000 mm; actual 0.1965 mm) (Pad 1 [GND] of C4 on F.Cu @ (86.53, 94.00 mm) — Via [Boot_Button] on F.Cu - B.Cu @ (85.58, 94.23 mm))
10. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2297 mm) (Track [VBUS] on F.Cu, length 0.7450 mm @ (155.03, 107.19 mm) — PTH pad [<no net>] of U1 @ (155.97, 107.87 mm))
11. **`clearance`**: Clearance violation ( clearance 0.2000 mm; actual 0.1740 mm) (Pad B8 [unconnected-(U1-SBU2-PadB8)] of U1 on F.Cu @ (154.85, 106.72 mm) — Track [VBUS] on F.Cu, length 0.2489 mm @ (154.85, 107.37 mm))
12. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2036 mm) (Track [VBUS] on F.Cu, length 0.2913 mm @ (155.53, 102.60 mm) — PTH pad [<no net>] of U1 @ (155.97, 102.08 mm))
13. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2036 mm) (Track [VBUS] on F.Cu, length 0.6540 mm @ (154.88, 102.60 mm) — PTH pad [<no net>] of U1 @ (155.97, 102.08 mm))
14. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2297 mm) (Track [VBUS] on F.Cu, length 0.0707 mm @ (155.77, 107.19 mm) — PTH pad [<no net>] of U1 @ (155.97, 107.87 mm))
15. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2135 mm) (Pad A4B9 [VBUS] of U1 on F.Cu @ (154.85, 107.37 mm) — PTH pad [<no net>] of U1 @ (155.97, 107.87 mm))
16. **`clearance`**: Clearance violation ( clearance 0.2000 mm; actual 0.1751 mm) (PTH pad [<no net>] of U1 @ (155.97, 102.08 mm) — Pad B1A12 [GND] of U1 on F.Cu @ (154.85, 101.77 mm))
17. **`hole_clearance`**: Hole clearance violation (board setup constraints hole clearance 0.2500 mm; actual 0.2099 mm) (Pad B4A9 [VBUS] of U1 on F.Cu @ (154.85, 102.57 mm) — PTH pad [<no net>] of U1 @ (155.97, 102.08 mm))
18. **`clearance`**: Clearance violation ( clearance 0.2000 mm; actual 0.1750 mm) (Pad A1B12 [GND] of U1 on F.Cu @ (154.85, 108.17 mm) — PTH pad [<no net>] of U1 @ (155.97, 107.87 mm))
19. **`courtyards_overlap`**: Courtyards overlap (Footprint C13 @ (128.10, 109.90 mm) — Footprint R9 @ (128.00, 111.30 mm))
20. **`courtyards_overlap`**: Courtyards overlap (Footprint R11 @ (133.00, 95.15 mm) — Footprint R10 @ (133.00, 92.20 mm))

_...and 29 more (see full JSON report artifact)._

</details>

<details><summary>⚠️ DRC Warnings</summary>

- `silk_overlap`: **60**
- `silk_over_copper`: **57**
- `lib_footprint_issues`: **44**
- `text_height`: **32**
- `text_thickness`: **31**
- `silk_edge_clearance`: **20**
- `padstack`: **8**
- `lib_footprint_mismatch`: **6**
- `net_conflict`: **4**
- `footprint_symbol_field_mismatch`: **2**

1. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of SW2 on F.Silkscreen @ (82.97, 119.50 mm))
2. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of SW2 on F.Silkscreen @ (84.73, 120.12 mm))
3. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (69.66, 94.98 mm) — Segment of U16 on F.Silkscreen @ (69.70, 95.70 mm))
4. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (69.66, 94.98 mm) — Segment of U16 on F.Silkscreen @ (69.70, 113.71 mm))
5. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (69.66, 94.98 mm) — Segment of U16 on F.Silkscreen @ (76.14, 95.70 mm))
6. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Arc on Edge.Cuts @ (157.16, 94.98 mm) — Reference field of U5 @ (162.60, 95.00 mm))
7. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of J2 on F.Silkscreen @ (90.00, 120.00 mm))
8. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of J2 on F.Silkscreen @ (90.00, 111.50 mm))
9. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of J2 on F.Silkscreen @ (105.23, 120.00 mm))
10. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of SW3 on F.Silkscreen @ (128.70, 118.58 mm))
11. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (74.66, 119.98 mm) — Segment of SW3 on F.Silkscreen @ (130.10, 120.15 mm))
12. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (157.16, 89.98 mm) — Segment of J1 on F.Silkscreen @ (90.00, 90.00 mm))
13. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (157.16, 89.98 mm) — Segment of J1 on F.Silkscreen @ (105.23, 98.50 mm))
14. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (157.16, 89.98 mm) — Segment of J1 on F.Silkscreen @ (105.23, 90.00 mm))
15. **`silk_edge_clearance`**: Silkscreen clipped by board edge (Segment on Edge.Cuts @ (162.16, 114.98 mm) — Segment of U1 on F.Silkscreen @ (162.28, 100.47 mm))

_...and 249 more (see full JSON report artifact)._

</details>
