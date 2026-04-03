"""
validator.py
------------
Validates uploaded PDFs to ensure they are the correct type
before running the pipeline.

Inspection PDF must contain structural markers our model depends on.
Thermal PDF must contain thermal scan markers.

Why validate?
  - Prevents pipeline failures mid-way through
  - Gives users clear feedback instead of cryptic errors
"""

import pdfplumber
import PyPDF2
import re


# ── Keywords that must appear in a valid inspection report ───────────────────

INSPECTION_REQUIRED = [
    "inspection",
    "impacted area",
    "negative side",
    "positive side",
]

INSPECTION_OPTIONAL = [
    "dampness", "leakage", "seepage", "checklist",
    "observation", "skirting", "plumbing", "structural"
]

# ── Keywords that must appear in a valid thermal report ──────────────────────

THERMAL_REQUIRED = [
    "hotspot",
    "coldspot",
    "emissivity",
]

THERMAL_OPTIONAL = [
    "thermal image", "reflected temperature", "device", "serial number"
]


def extract_text_for_validation(pdf_path: str, max_pages: int = 10) -> str:
    """
    Extract text from first N pages for validation.
    Tries pdfplumber first, falls back to PyPDF2.
    Strips null bytes for UTF-16 encoded PDFs.
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_pages]:
                t = page.extract_text() or ""
                text += t + " "
    except Exception:
        pass

    # Fallback to PyPDF2 if pdfplumber got nothing
    if len(text.strip()) < 50:
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages[:max_pages]:
                    t = page.extract_text() or ""
                    text += t.replace("\x00", "") + " "
        except Exception:
            pass

    return text.lower()


def validate_inspection_pdf(pdf_path: str) -> tuple:
    """
    Validate that the uploaded file is a property inspection report.
    Returns (is_valid: bool, message: str, score: int)
    score = number of required keywords found
    """
    text = extract_text_for_validation(pdf_path)

    if len(text.strip()) < 100:
        return False, "Could not extract text from the PDF. The file may be scanned or corrupted.", 0

    # Check required keywords
    missing = [kw for kw in INSPECTION_REQUIRED if kw not in text]
    found   = [kw for kw in INSPECTION_REQUIRED if kw in text]
    optional_found = sum(1 for kw in INSPECTION_OPTIONAL if kw in text)

    score = len(found) + optional_found

    if len(missing) > 1:
        return (
            False,
            f"This does not appear to be a valid property inspection report. "
            f"Expected structural markers not found: {', '.join(missing)}. "
            f"Please upload a property inspection PDF with area-wise observations.",
            score
        )

    return True, "Valid inspection report.", score


def validate_thermal_pdf(pdf_path: str) -> tuple:
    """
    Validate that the uploaded file is a thermal imaging report.
    Returns (is_valid: bool, message: str, score: int)
    """
    # For thermal PDFs, use PyPDF2 directly (handles UTF-16 encoding)
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:5]:
                t = page.extract_text() or ""
                text += t.replace("\x00", "") + " "
    except Exception:
        pass

    # Also try pdfplumber as fallback
    if len(text.strip()) < 50:
        text = extract_text_for_validation(pdf_path)

    text_lower = text.lower()

    if len(text_lower.strip()) < 50:
        return False, "Could not extract text from the thermal PDF. The file may be corrupted.", 0

    missing = [kw for kw in THERMAL_REQUIRED if kw not in text_lower]
    found   = [kw for kw in THERMAL_REQUIRED if kw in text_lower]
    optional_found = sum(1 for kw in THERMAL_OPTIONAL if kw in text_lower)

    score = len(found) + optional_found

    if len(missing) > 1:
        return (
            False,
            f"This does not appear to be a valid thermal imaging report. "
            f"Expected thermal markers not found: {', '.join(missing)}. "
            f"Please upload a thermal scan PDF with hotspot/coldspot temperature data.",
            score
        )

    return True, "Valid thermal report.", score


def validate_both(inspection_path: str, thermal_path: str) -> tuple:
    """
    Validate both PDFs. Returns (is_valid, error_message).
    """
    insp_valid, insp_msg, insp_score = validate_inspection_pdf(inspection_path)
    if not insp_valid:
        return False, f"Inspection PDF rejected: {insp_msg}"

    therm_valid, therm_msg, therm_score = validate_thermal_pdf(thermal_path)
    if not therm_valid:
        return False, f"Thermal PDF rejected: {therm_msg}"

    # Check they weren't swapped
    insp_text  = extract_text_for_validation(inspection_path)
    therm_text = extract_text_for_validation(thermal_path)

    if "hotspot" in insp_text and "impacted area" not in insp_text:
        return False, "It looks like you uploaded the thermal PDF as the inspection report. Please swap the files."

    if "impacted area" in therm_text and "hotspot" not in therm_text:
        return False, "It looks like you uploaded the inspection PDF as the thermal report. Please swap the files."

    return True, "Both files validated successfully."
