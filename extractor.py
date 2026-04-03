"""
extractor.py
------------
Handles all PDF data extraction:
- Text extraction from Inspection Report
- Thermal data parsing from Thermal Images PDF
- Image extraction from both PDFs using PyMuPDF
"""

import os
import fitz          # PyMuPDF - for image extraction
import pdfplumber    # for layout-aware text extraction
import re


# ── Folder where all extracted images will be saved ──────────────────────────
TEMP_IMAGE_DIR = "temp_images"


def ensure_temp_dir():
    """Create temp_images folder if it doesn't exist."""
    if not os.path.exists(TEMP_IMAGE_DIR):
        os.makedirs(TEMP_IMAGE_DIR)
        print(f"Created folder: {TEMP_IMAGE_DIR}/")


# ── 1. Extract text from Inspection Report ───────────────────────────────────

def extract_inspection_text(pdf_path: str) -> dict:
    """
    Extract text from the inspection report PDF page by page.
    Returns a dict with:
      - 'full_text': entire text as one string
      - 'pages': list of per-page text
      - 'summary_table': the summary table section if found
    """
    pages = []
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page": i + 1, "text": text})
            full_text += f"\n--- Page {i+1} ---\n{text}"

    # Try to isolate the summary table section
    summary_table = ""
    if "SUMMARY TABLE" in full_text.upper():
        start = full_text.upper().find("SUMMARY TABLE")
        # grab next 3000 chars after the heading as the summary block
        summary_table = full_text[start:start + 3000]

    print(f"Inspection report: {len(pages)} pages extracted")
    return {
        "full_text": full_text,
        "pages": pages,
        "summary_table": summary_table
    }


# ── 2. Extract thermal data from Thermal Images PDF ──────────────────────────

def extract_thermal_data(pdf_path: str) -> list:
    """
    Extract temperature metadata from each page of the thermal PDF using PyPDF2.
    PyPDF2 can read the text overlay on thermal pages (pdfplumber cannot).
    Returns a list of dicts, one per thermal image page.
    """
    import PyPDF2

    thermal_records = []

    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)

        for i, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            # Clean UTF-16 null bytes that PyPDF2 sometimes leaves in
            text = raw.replace("\x00", "")

            record = {
                "page": i + 1,
                "raw_text": text,
                "hotspot": None,
                "coldspot": None,
                "emissivity": None,
                "date": None,
                "image_file": None,
                "image_path": None   # filled after image extraction
            }

            # Parse hotspot temperature
            match = re.search(r"Hotspot\s*:\s*([\d.]+\s*°C)", text)
            if match:
                record["hotspot"] = match.group(1).strip()

            # Parse coldspot temperature
            match = re.search(r"Coldspot\s*:\s*([\d.]+\s*°C)", text)
            if match:
                record["coldspot"] = match.group(1).strip()

            # Parse emissivity
            match = re.search(r"Emissivity\s*:\s*([\d.]+)", text)
            if match:
                record["emissivity"] = match.group(1).strip()

            # Parse date
            match = re.search(r"(\d{2}/\d{2}/\d{2,4})", text)
            if match:
                record["date"] = match.group(1).strip()

            # Parse source image filename
            match = re.search(r"Thermal image\s*:\s*(\S+\.JPG)", text, re.IGNORECASE)
            if match:
                record["image_file"] = match.group(1).strip()

            thermal_records.append(record)

    print(f"Thermal report: {len(thermal_records)} thermal records extracted")
    return thermal_records


# ── 3. Extract embedded images from a PDF ────────────────────────────────────

def extract_images_from_pdf(pdf_path: str, prefix: str, largest_only: bool = True) -> list:
    """
    Extract embedded images from a PDF using PyMuPDF.
    largest_only=True: saves only the largest image per page (avoids tiny fragments).
    largest_only=False: saves all images (use for inspection report photos).
    Returns a list of saved image file paths.
    """
    ensure_temp_dir()
    saved_paths = []

    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        if not image_list:
            continue

        if largest_only:
            # Thermal PDFs share image xrefs across all pages (PDF optimization).
            # get_images() returns the same pool for every page.
            # Solution: render the page directly to a PNG — this always gives
            # the correct visual for that specific page.
            try:
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for good resolution
                pix = page.get_pixmap(matrix=mat)
                filename = f"{prefix}_page{page_num + 1}.png"
                filepath = os.path.join(TEMP_IMAGE_DIR, filename)
                pix.save(filepath)
                saved_paths.append(filepath)
            except Exception as e:
                print(f"  Skipped render on page {page_num+1}: {e}")
        else:
            # Save all images on the page
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_ext = base_image["ext"]
                    filename = f"{prefix}_page{page_num + 1}_img{img_index + 1}.{image_ext}"
                    filepath = os.path.join(TEMP_IMAGE_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(base_image["image"])
                    saved_paths.append(filepath)
                except Exception as e:
                    print(f"  Skipped image on page {page_num+1}, index {img_index}: {e}")

    doc.close()
    print(f"Images extracted from '{prefix}' PDF: {len(saved_paths)} images saved to {TEMP_IMAGE_DIR}/")
    return saved_paths


# ── 4. Match thermal images to their records ─────────────────────────────────

def match_thermal_images(thermal_records: list, thermal_image_paths: list) -> list:
    """
    Match extracted image files to their thermal records by page number.
    Updates each thermal record with the actual saved image path.
    """
    # Group image paths by page number
    page_images = {}
    for path in thermal_image_paths:
        # filename format: thermal_page{N}_img{M}.ext
        match = re.search(r"page(\d+)", path)
        if match:
            page_num = int(match.group(1))
            if page_num not in page_images:
                page_images[page_num] = []
            page_images[page_num].append(path)

    # Assign first image of each page to the thermal record
    for record in thermal_records:
        page = record["page"]
        if page in page_images:
            record["image_path"] = page_images[page][0]

    matched = sum(1 for r in thermal_records if r["image_path"])
    print(f"Thermal images matched to records: {matched}/{len(thermal_records)}")
    return thermal_records


# ── 5. Run all extractions together ──────────────────────────────────────────

def extract_all(inspection_pdf: str, thermal_pdf: str) -> dict:
    """
    Master function — runs all extractions and returns everything needed
    for the AI report generation step.
    """
    print("\n=== Starting Extraction ===\n")

    # Extract inspection text
    inspection_data = extract_inspection_text(inspection_pdf)

    # Extract thermal text data
    thermal_records = extract_thermal_data(thermal_pdf)

    # Extract images from both PDFs
    # inspection: keep all images (they are the actual site photos)
    # thermal: keep only largest per page (one thermal scan per page)
    inspection_images = extract_images_from_pdf(inspection_pdf, prefix="inspection", largest_only=False)
    thermal_images    = extract_images_from_pdf(thermal_pdf,    prefix="thermal",    largest_only=True)

    # Match thermal images to their records
    thermal_records = match_thermal_images(thermal_records, thermal_images)

    print("\n=== Extraction Complete ===\n")

    return {
        "inspection": inspection_data,
        "thermal_records": thermal_records,
        "inspection_images": inspection_images,
        "thermal_images": thermal_images
    }


# ── Quick test when run directly ─────────────────────────────────────────────

if __name__ == "__main__":
    result = extract_all(
        inspection_pdf="Sample Report.pdf",
        thermal_pdf="Thermal Images.pdf"
    )

    print("\n--- Inspection Text Sample (first 500 chars) ---")
    print(result["inspection"]["full_text"][:500])

    print("\n--- First 3 Thermal Records ---")
    for r in result["thermal_records"][:3]:
        print(r)

    print("\n--- Total inspection images:", len(result["inspection_images"]))
    print("--- Total thermal images:   ", len(result["thermal_images"]))
