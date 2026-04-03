"""
prompt_builder.py
-----------------
Assembles structured inspection + thermal data into a single
prompt string ready to be sent to the Groq LLM.

Why a separate file?
  - Prompt tuning is frequent during development
  - Keeping it separate means you never touch the API code to fix output quality
  - Easy to test prompt output without making API calls
"""


def build_prompt(structured: dict) -> str:
    """
    Build the full DDR generation prompt from structured data.
    Returns a single string to send to the LLM.
    """

    info     = structured["property_info"]
    areas    = structured["impacted_areas"]
    summary  = structured["summary_raw"]
    check    = structured["checklist"]
    thermal  = structured["thermal_summary"]

    # ── Section 1: Role and Task ──────────────────────────────────────────────
    role = """You are an expert property inspection report writer.
Your task is to generate a Detailed Diagnostic Report (DDR) for a residential property.
You will be given:
  1. Inspection report data (observations, checklist, summary)
  2. Thermal imaging scan data (temperature readings from 30 scans)

STRICT RULES:
- Do NOT invent any facts not present in the provided data
- If information is missing, write exactly: Not Available
- If information conflicts, mention the conflict clearly
- Use simple, client-friendly language — avoid heavy technical jargon
- Be precise and factual
- Each section must be clearly labeled exactly as shown below
"""

    # ── Section 2: Property Information ──────────────────────────────────────
    property_block = f"""
=== PROPERTY INFORMATION (INPUT DATA) ===
Inspection Date     : {info['inspection_date']}
Inspected By        : {info['inspected_by']}
Property Type       : {info['property_type']}
Floors in Building  : {info['floors']}
Property Age        : {info['property_age']}
Inspection Score    : {info['score']}
Previous Audit Done : {info['previous_audit']}
Previous Repair Done: {info['previous_repair']}
"""

    # ── Section 3: Impacted Areas ─────────────────────────────────────────────
    areas_block = "\n=== IMPACTED AREAS (INPUT DATA) ===\n"
    for area in areas:
        areas_block += f"""
Area {area['area_number']}:
  Problem Observed (Negative Side) : {area['negative_description']}
  Source / Cause Location (Positive Side): {area['positive_description']}
"""

    # ── Section 4: Summary Table ──────────────────────────────────────────────
    summary_block = f"""
=== INSPECTION SUMMARY TABLE (INPUT DATA) ===
{summary}
"""

    # ── Section 5: Checklist Findings ────────────────────────────────────────
    checklist_block = f"""
=== CHECKLIST FINDINGS (INPUT DATA) ===
Leakage Timing              : {check['leakage_timing']}
Concealed Plumbing Issue    : {check['concealed_plumbing']}
Tile Joint Gaps Observed    : {check['tile_gaps']}
RCC Structural Condition    : {check['structural_condition']}
External Wall Cracks        : {check['external_wall_cracks']}
Algae / Fungus on Walls     : {check['algae_fungus']}
"""

    # ── Section 6: Thermal Data ───────────────────────────────────────────────
    thermal_block = f"""
=== THERMAL IMAGING DATA (INPUT DATA) ===
{thermal}

THERMAL INTERPRETATION GUIDE:
- Hotspot temperature significantly higher than coldspot = moisture/dampness present
- Readings marked [HIGH] (>=27 deg C hotspot) indicate active moisture zones
- Emissivity 0.94 is standard for building surfaces
- All scans taken on same day as inspection (27/09/2022)
"""

    # ── Section 7: Output Instructions ───────────────────────────────────────
    output_instructions = """
=== YOUR TASK: GENERATE THE DDR ===

Using ALL the input data above, generate a complete Detailed Diagnostic Report.
Structure your output EXACTLY as follows — use these exact section headings:

---DDR START---

## 1. PROPERTY ISSUE SUMMARY
Write a 3-5 sentence executive summary of the overall property condition.
Mention the inspection score, main problem type, and overall severity.

## 2. AREA-WISE OBSERVATIONS
For each impacted area, write:
- Area name and location
- What problem was observed (negative side)
- Where the source/cause is (positive side)
- Supporting thermal data if relevant (mention hotspot temperatures)
- Severity: Low / Moderate / High

## 3. PROBABLE ROOT CAUSE
Explain the most likely root cause(s) of the problems observed.
Link inspection findings with thermal data to support your reasoning.

## 4. SEVERITY ASSESSMENT
Overall severity: Low / Moderate / High
Provide reasoning for the severity rating.
List the top 3 most critical issues found.

## 5. RECOMMENDED ACTIONS
List specific recommended actions in priority order (most urgent first).
For each action mention: what to do, where, and why.

## 6. ADDITIONAL NOTES
Any other observations, conflicts in data, or important points not covered above.

## 7. MISSING OR UNCLEAR INFORMATION
List any information that was expected but not available in the provided data.
Write "None" if all required information was present.

---DDR END---
"""

    # ── Assemble full prompt ──────────────────────────────────────────────────
    full_prompt = (
        role
        + property_block
        + areas_block
        + summary_block
        + checklist_block
        + thermal_block
        + output_instructions
    )

    return full_prompt


# ── Quick test: print prompt length and preview ───────────────────────────────

if __name__ == "__main__":
    from extractor import extract_all
    from structurer import structure_all

    extracted  = extract_all("Sample Report.pdf", "Thermal Images.pdf")
    structured = structure_all(extracted)
    prompt     = build_prompt(structured)

    print(f"Prompt length : {len(prompt)} characters")
    print(f"Approx tokens : ~{len(prompt)//4} tokens")
    print()
    print("--- PROMPT PREVIEW (first 1000 chars) ---")
    print(prompt[:1000])
    print("...")
    print("--- PROMPT PREVIEW (last 500 chars) ---")
    print(prompt[-500:])
