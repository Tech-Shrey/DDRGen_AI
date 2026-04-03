"""
app.py
------
Flask web application for DDRGen AI.
Handles file uploads, runs the pipeline, serves the report viewer and download.
"""

import os
import uuid
import threading
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Track job status in memory
jobs = {}

# Max upload size: 50MB per file
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


def run_pipeline_job(job_id, inspection_path, thermal_path, output_path):
    """Run the full DDR pipeline in a background thread."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["step"]   = "Extracting data from PDFs..."

        from extractor        import extract_all
        from structurer       import structure_all
        from prompt_builder   import build_prompt
        from ai_generator     import generate_ddr, extract_ddr_sections
        from report_generator import generate_report

        jobs[job_id]["step"] = "Extracting text and images from PDFs..."
        extracted = extract_all(inspection_path, thermal_path)

        jobs[job_id]["step"] = "Structuring extracted data..."
        structured = structure_all(extracted)

        jobs[job_id]["step"] = "Building AI prompt..."
        prompt = build_prompt(structured)

        jobs[job_id]["step"] = "Generating DDR with AI (this takes ~60 seconds)..."
        ddr_text = generate_ddr(prompt)
        sections = extract_ddr_sections(ddr_text)

        jobs[job_id]["step"] = "Generating Word report..."
        generate_report(sections, structured, output_path)

        jobs[job_id]["status"]   = "done"
        jobs[job_id]["step"]     = "Complete"
        jobs[job_id]["sections"] = sections
        jobs[job_id]["property"] = structured["property_info"]

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = str(e)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    inspection_file = request.files.get("inspection")
    thermal_file    = request.files.get("thermal")

    if not inspection_file or not thermal_file:
        return render_template("index.html", error="Please upload both PDF files.")

    if not inspection_file.filename.endswith(".pdf") or not thermal_file.filename.endswith(".pdf"):
        return render_template("index.html", error="Both files must be PDF format.")

    # Save uploaded files with unique names
    job_id = str(uuid.uuid4())[:8]
    inspection_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_inspection.pdf")
    thermal_path    = os.path.join(UPLOAD_FOLDER, f"{job_id}_thermal.pdf")
    output_path     = os.path.join(OUTPUT_FOLDER, f"{job_id}_DDR_Report.docx")

    inspection_file.save(inspection_path)
    thermal_file.save(thermal_path)

    # ── Validate PDFs before running pipeline ─────────────────────────────────
    from validator import validate_both

    is_valid, error_msg = validate_both(inspection_path, thermal_path)
    if not is_valid:
        os.remove(inspection_path)
        os.remove(thermal_path)
        return render_template("index.html", error=error_msg)

    # Init job
    jobs[job_id] = {
        "status":      "queued",
        "step":        "Starting...",
        "output_path": output_path,
        "sections":    None,
        "property":    None,
        "error":       None,
    }

    # Run pipeline in background thread so browser doesn't time out
    thread = threading.Thread(
        target=run_pipeline_job,
        args=(job_id, inspection_path, thermal_path, output_path)
    )
    thread.daemon = True
    thread.start()

    return redirect(url_for("processing", job_id=job_id))


@app.route("/processing/<job_id>")
def processing(job_id):
    if job_id not in jobs:
        return redirect(url_for("index"))
    return render_template("processing.html", job_id=job_id)


@app.route("/status/<job_id>")
def status(job_id):
    """JSON endpoint polled by the processing page."""
    if job_id not in jobs:
        return jsonify({"status": "not_found"})
    job = jobs[job_id]
    return jsonify({
        "status": job["status"],
        "step":   job["step"],
        "error":  job.get("error"),
    })


@app.route("/report/<job_id>")
def report(job_id):
    if job_id not in jobs or jobs[job_id]["status"] != "done":
        return redirect(url_for("index"))
    sections = jobs[job_id]["sections"]
    property_info = jobs[job_id]["property"]
    return render_template("report.html",
                           job_id=job_id,
                           sections=sections,
                           property_info=property_info)


@app.route("/download/<job_id>")
def download(job_id):
    if job_id not in jobs:
        return redirect(url_for("index"))
    output_path = jobs[job_id]["output_path"]
    if not os.path.exists(output_path):
        return "Report not found", 404
    return send_file(output_path,
                     as_attachment=True,
                     download_name="DDR_Report.docx")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
