"""
main.py
-------
DDRGen AI — Detailed Diagnostic Report Generator
Single entry point for the full pipeline.

Usage:
    python main.py
    python main.py --inspection "Sample Report.pdf" --thermal "Thermal Images.pdf"
    python main.py --inspection "path/to/report.pdf" --thermal "path/to/thermal.pdf" --output "MyReport.docx"
"""

import argparse
import os
import sys
import time

from extractor      import extract_all
from structurer     import structure_all
from prompt_builder import build_prompt
from ai_generator   import generate_ddr, extract_ddr_sections
from report_generator import generate_report


# ── Argument Parser ───────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="DDRGen AI — Generate a Detailed Diagnostic Report from inspection + thermal PDFs"
    )
    parser.add_argument(
        "--inspection",
        default="Sample Report.pdf",
        help="Path to the inspection report PDF (default: Sample Report.pdf)"
    )
    parser.add_argument(
        "--thermal",
        default="Thermal Images.pdf",
        help="Path to the thermal images PDF (default: Thermal Images.pdf)"
    )
    parser.add_argument(
        "--output",
        default="DDR_Report.docx",
        help="Output file name for the Word report (default: DDR_Report.docx)"
    )
    return parser.parse_args()


# ── Validation ────────────────────────────────────────────────────────────────

def validate_inputs(inspection_pdf, thermal_pdf):
    """Check input files exist before starting the pipeline."""
    errors = []
    if not os.path.exists(inspection_pdf):
        errors.append(f"Inspection PDF not found: '{inspection_pdf}'")
    if not os.path.exists(thermal_pdf):
        errors.append(f"Thermal PDF not found: '{thermal_pdf}'")
    if not os.getenv("GROQ_API_KEY"):
        errors.append("GROQ_API_KEY not set in .env file")
    return errors


# ── Step Logger ───────────────────────────────────────────────────────────────

def step(number, total, label):
    print(f"\n[{number}/{total}] {label}")
    print("-" * 50)


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(inspection_pdf, thermal_pdf, output_path):
    total_steps = 5
    start_time  = time.time()

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    step(1, total_steps, "Extracting data from PDFs")
    extracted = extract_all(inspection_pdf, thermal_pdf)

    inspection_pages  = len(extracted["inspection"]["pages"])
    thermal_count     = len(extracted["thermal_records"])
    inspection_images = len(extracted["inspection_images"])
    thermal_images    = len(extracted["thermal_images"])

    print(f"  Inspection pages  : {inspection_pages}")
    print(f"  Thermal records   : {thermal_count}")
    print(f"  Inspection images : {inspection_images}")
    print(f"  Thermal images    : {thermal_images}")

    # ── Step 2: Structure ─────────────────────────────────────────────────────
    step(2, total_steps, "Structuring extracted data")
    structured = structure_all(extracted)

    print(f"  Property fields   : {sum(1 for v in structured['property_info'].values() if v != 'Not Available')}/{len(structured['property_info'])}")
    print(f"  Impacted areas    : {len(structured['impacted_areas'])}")
    print(f"  Thermal formatted : {len(structured['thermal_records'])}")

    # ── Step 3: Build Prompt ──────────────────────────────────────────────────
    step(3, total_steps, "Building AI prompt")
    prompt = build_prompt(structured)
    print(f"  Prompt length     : {len(prompt)} characters")
    print(f"  Estimated tokens  : ~{len(prompt)//4}")

    # ── Step 4: Generate DDR via AI ───────────────────────────────────────────
    step(4, total_steps, "Generating DDR with Groq LLM")
    ddr_text = generate_ddr(prompt)
    sections = extract_ddr_sections(ddr_text)

    filled = sum(1 for k, v in sections.items() if k != "full_text" and v.strip())
    print(f"  DDR sections filled: {filled}/7")

    # ── Step 5: Generate Word Report ──────────────────────────────────────────
    step(5, total_steps, "Generating Word report")
    output = generate_report(sections, structured, output_path)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    file_kb  = os.path.getsize(output) / 1024

    print("\n" + "=" * 50)
    print("  DDRGen AI — COMPLETE")
    print("=" * 50)
    print(f"  Output file : {output}")
    print(f"  File size   : {file_kb:.1f} KB")
    print(f"  Time taken  : {elapsed:.1f} seconds")
    print("=" * 50)

    return output


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    args = parse_args()

    print("=" * 50)
    print("  DDRGen AI — Detailed Diagnostic Report Generator")
    print("=" * 50)
    print(f"  Inspection PDF : {args.inspection}")
    print(f"  Thermal PDF    : {args.thermal}")
    print(f"  Output file    : {args.output}")

    # Validate
    errors = validate_inputs(args.inspection, args.thermal)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Run
    try:
        run_pipeline(args.inspection, args.thermal, args.output)
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nPipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
