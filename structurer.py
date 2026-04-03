"""
structurer.py
-------------
Transforms raw extracted data into clean structured sections
ready to be fed into the AI prompt.

Input  : output from extractor.py (raw text + thermal records + image paths)
Output : a single structured dict with all sections clearly labeled
"""

import re


# ── 1. Parse Property Info from Page 1 ───────────────────────────────────────

def parse_property_info(full_text: str) -> dict:
    """
    Extract basic property details from the inspection report header.
    These appear on page 1.
    """
    info = {
        "inspection_date": "Not Available",
        "inspected_by":    "Not Available",
        "property_type":   "Not Available",
        "floors":          "Not Available",
        "property_age":    "Not Available",
        "score":           "Not Available",
        "previous_audit":  "Not Available",
        "previous_repair": "Not Available",
    }

    patterns = {
        "inspection_date": r"Inspection Date and Time[:\s]+([\d./:\s]+IST)",
        "inspected_by":    r"Inspected By[:\s]+(.+)",
        "property_type":   r"Property Type[:\s]+(.+)",
        "floors":          r"Floors[:\s]+([\d]+)",
        "property_age":    r"Property Age.*?[:\s]+([\d]+)",
        "score":           r"Score\s+([\d.]+%)",
        "previous_audit":  r"Previous Structural audit done\s+(\w+)",
        "previous_repair": r"Previous Repair work done\s+(\w+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()

    return info


# ── 2. Parse Impacted Areas ───────────────────────────────────────────────────

def parse_impacted_areas(full_text: str) -> list:
    """
    Extract each impacted area with its negative side (problem found)
    and positive side (source/cause location).
    Returns a list of area dicts.
    """
    areas = []

    # Split text around "Impacted Area" markers
    splits = re.split(r"Impacted\s+Area\s+\d+", full_text, flags=re.IGNORECASE)

    # First split is the header, skip it
    for i, block in enumerate(splits[1:], start=1):
        area = {
            "area_number": i,
            "negative_description": "Not Available",
            "positive_description": "Not Available",
        }

        # Negative side (problem observed)
        neg = re.search(
            r"Negative\s+side\s+Description\s+(.+?)(?:Negative\s+side\s+photographs|Photo\s+\d|Positive\s+side\s+Description|Site\s+Details|$)",
            block, re.IGNORECASE | re.DOTALL
        )
        if neg:
            desc = neg.group(1).strip()
            # Remove trailing photo references
            desc = re.sub(r'\s*Photo\s+\d+.*', '', desc, flags=re.IGNORECASE | re.DOTALL).strip()
            area["negative_description"] = desc if desc else "Not Available"

        # Positive side (source/cause) — stop before photo list
        pos = re.search(
            r"Positive\s+side\s+Description\s+(.+?)(?:Positive\s+side\s+photographs|Photo\s+\d|Impacted\s+Area|\Z)",
            block, re.IGNORECASE | re.DOTALL
        )
        if pos:
            desc = pos.group(1).strip()
            desc = re.sub(r'\s*Photo\s+\d+.*', '', desc, flags=re.IGNORECASE | re.DOTALL).strip()
            area["positive_description"] = desc if desc else "Not Available"

        areas.append(area)

    return areas


# ── 3. Parse Summary Table ────────────────────────────────────────────────────

def parse_summary_table(summary_raw: str) -> list:
    """
    Parse the summary table into a list of point dicts.
    Each point has: point_no, impacted_area (negative), exposed_area (positive).
    """
    points = []

    if not summary_raw:
        return points

def parse_summary_table(summary_raw: str) -> list:
    """
    Parse the summary table into a list of point dicts.
    Uses the full summary block to extract negative and positive observations.
    """
    points = []

    if not summary_raw:
        return points

    # Clean up extra spaces from PDF extraction artifacts
    cleaned = re.sub(r'\s+', ' ', summary_raw)

    # Negative points: single or double digit numbers only (not flat numbers like 103)
    neg_points = re.findall(r'(?<!\d)([1-9]|[1-9]\d)\s+(Observed\s+[^0-9]{15,200}?)(?=\d|\Z)', cleaned, re.IGNORECASE)
    pos_points = re.findall(r'([1-9]\.\d+)\s+(Observed\s+[^0-9]{15,200}?)(?=\d|\Z)', cleaned, re.IGNORECASE)

    pos_lookup = {sub.strip(): desc.strip() for sub, desc in pos_points}

    for point_no, neg_desc in neg_points:
        sub_key = f"{point_no}.1"
        points.append({
            "point_no":      point_no.strip(),
            "negative_side": neg_desc.strip(),
            "sub_point":     sub_key,
            "positive_side": pos_lookup.get(sub_key, "Not Available"),
        })

    return points

    return points


# ── 4. Parse Checklist Results ────────────────────────────────────────────────

def parse_checklist(full_text: str) -> dict:
    """
    Extract key checklist findings — leakage type, plumbing issues,
    structural condition, external wall condition.
    """
    checklist = {
        "leakage_timing":        "Not Available",
        "concealed_plumbing":    "Not Available",
        "tile_gaps":             "Not Available",
        "structural_condition":  "Not Available",
        "external_wall_cracks":  "Not Available",
        "algae_fungus":          "Not Available",
    }

    patterns = {
        "leakage_timing":       r"Leakage during[:\s]+(All time|Rainy season|Specific time)",
        "concealed_plumbing":   r"Leakage due to concealed plumbing\s+(Yes|No)",
        "tile_gaps":            r"Gaps/Blackish dirt Observed in tile joints\s+(Yes|No)",
        "structural_condition": r"Condition of cracks observed on RCC Column and Beam\s+(\w+)",
        "external_wall_cracks": r"Are there any major or minor cracks observed[^\n]+?\n\s+(\w+)",
        "algae_fungus":         r"Algae fungus and Moss observed[^\n]+?\n\s+(\w+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            checklist[key] = match.group(1).strip()

    return checklist


# ── 5. Format Thermal Records ─────────────────────────────────────────────────

def format_thermal_summary(thermal_records: list) -> str:
    """
    Convert thermal records list into a clean readable text block
    for the AI prompt. Groups records and highlights high hotspot readings.
    """
    lines = ["THERMAL SCAN SUMMARY", "=" * 40]
    lines.append(f"Total thermal images: {len(thermal_records)}")
    lines.append(f"Device: GTC 400 C Professional")
    lines.append(f"Emissivity: 0.94 | Reflected Temp: 23°C")
    lines.append("")

    for r in thermal_records:
        hotspot  = r.get("hotspot")  or "N/A"
        coldspot = r.get("coldspot") or "N/A"
        date     = r.get("date")     or "N/A"
        imgfile  = r.get("image_file") or f"Page {r['page']}"

        # Flag readings above 27°C as potentially significant
        flag = ""
        try:
            temp_val = float(hotspot.replace("°C", "").strip())
            if temp_val >= 27.0:
                flag = " [HIGH]"
        except:
            pass

        lines.append(
            f"Scan {r['page']:02d} | {imgfile} | "
            f"Hotspot: {hotspot}{flag} | Coldspot: {coldspot} | Date: {date}"
        )

    return "\n".join(lines)


# ── 6. Map Thermal Scans to Inspection Areas ──────────────────────────────────

def map_thermal_to_areas(thermal_records: list, num_areas: int) -> dict:
    """
    Distribute thermal scans evenly across inspection areas.
    Since we have 30 scans and 7 areas, each area gets ~4 scans.
    Returns dict: {area_number: [thermal_record, ...]}
    """
    mapping = {}
    scans_per_area = max(1, len(thermal_records) // num_areas)

    for i in range(num_areas):
        start = i * scans_per_area
        end   = start + scans_per_area if i < num_areas - 1 else len(thermal_records)
        mapping[i + 1] = thermal_records[start:end]

    return mapping


# ── 7. Master structuring function ───────────────────────────────────────────

def structure_all(extracted: dict) -> dict:
    """
    Takes the full output from extractor.extract_all() and returns
    a clean structured dict ready for the AI prompt builder.
    """
    print("\n=== Starting Data Structuring ===\n")

    full_text       = extracted["inspection"]["full_text"]
    summary_raw     = extracted["inspection"]["summary_table"]
    thermal_records = extracted["thermal_records"]

    # Parse all sections
    property_info   = parse_property_info(full_text)
    impacted_areas  = parse_impacted_areas(full_text)
    # For summary table — pass raw text to AI rather than brittle regex parsing
    # The AI handles messy PDF text far better than regex
    summary_points  = parse_summary_table(summary_raw)
    # Always include raw summary for AI fallback
    raw_summary     = summary_raw
    checklist       = parse_checklist(full_text)
    thermal_summary = format_thermal_summary(thermal_records)
    thermal_map     = map_thermal_to_areas(thermal_records, len(impacted_areas) or 7)

    print(f"Property info fields populated : {sum(1 for v in property_info.values() if v != 'Not Available')}/{len(property_info)}")
    print(f"Impacted areas parsed          : {len(impacted_areas)}")
    print(f"Summary table points           : {len(summary_points)}")
    print(f"Checklist fields populated     : {sum(1 for v in checklist.values() if v != 'Not Available')}/{len(checklist)}")
    print(f"Thermal records formatted      : {len(thermal_records)}")

    print("\n=== Data Structuring Complete ===\n")

    return {
        "property_info":        property_info,
        "impacted_areas":       impacted_areas,
        "summary_points":       summary_points,
        "summary_raw":          raw_summary,
        "checklist":            checklist,
        "thermal_summary":      thermal_summary,
        "thermal_map":          thermal_map,
        "inspection_images":    extracted["inspection_images"],
        "thermal_records":      thermal_records,
    }


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from extractor import extract_all

    extracted  = extract_all("Sample Report.pdf", "Thermal Images.pdf")
    structured = structure_all(extracted)

    print("-- Property Info --")
    for k, v in structured["property_info"].items():
        print(f"  {k}: {v}")

    print("\n-- Impacted Areas --")
    for area in structured["impacted_areas"]:
        print(f"  Area {area['area_number']}:")
        print(f"    Problem : {area['negative_description'][:80]}")
        print(f"    Source  : {area['positive_description'][:80]}")

    print("\n-- Summary Table Points --")
    for p in structured["summary_points"]:
        print(f"  {p['point_no']}. {p['negative_side'][:70]}")

    print("\n-- Checklist --")
    for k, v in structured["checklist"].items():
        print(f"  {k}: {v}")

    print("\n-- Thermal Summary (first 8 lines) --")
    lines = structured["thermal_summary"].split("\n")
    for line in lines[:8]:
        print(" ", line)
