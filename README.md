# DDRGen AI — Detailed Diagnostic Report Generator

An AI-powered pipeline that reads a property inspection report and a thermal
imaging report, then automatically generates a structured, client-friendly
Detailed Diagnostic Report (DDR) as a formatted Word document with embedded
inspection photos and thermal scan images.

---

## The Problem This Solves

Property inspection engineers produce two separate documents after a site visit:
1. An inspection report — text observations, checklists, site photographs
2. A thermal imaging report — temperature scans showing moisture/heat anomalies

Manually combining these into a single client-ready DDR is time-consuming,
error-prone, and requires the engineer to cross-reference both documents while
writing. This system automates that entire process — from raw PDFs to a
formatted Word report — in under 2 minutes.

---

## What It Does

Takes two PDF inputs:
- A property inspection report (observations, checklists, area-wise findings, photos)
- A thermal imaging report (30 thermal scans with hotspot/coldspot temperature data)

Produces one output:
- A formatted `.docx` Word report with a cover page, 7 structured DDR sections,
  inspection photographs, and thermal scan images placed under their relevant findings

---

## Project Structure

```
DDRGen AI/
├── main.py               # Single entry point — run this
├── extractor.py          # Phase 3: PDF text + image extraction
├── structurer.py         # Phase 4: data parsing and structuring
├── prompt_builder.py     # Phase 5: AI prompt assembly
├── ai_generator.py       # Phase 5: Groq API call + DDR section parsing
├── report_generator.py   # Phase 6: Word document generation
├── requirements.txt      # All dependencies
├── .env                  # API key storage (never commit this)
├── .gitignore            # Protects .env and venv/
├── dev_notes.md          # Development decisions and notes
├── temp_images/          # Auto-created during extraction, holds extracted images
├── DDR_Report.docx       # Generated output report
├── Sample Report.pdf     # Sample inspection report (input)
├── Thermal Images.pdf    # Sample thermal report (input)
└── Ai Generalist - Assignments.pdf  # Assignment brief
```

---

## Setup

### Prerequisites
- Python 3.10 or higher
- A free Groq API key — sign up at https://console.groq.com (no billing required)

### Step 1 — Create virtual environment
```bash
python -m venv venv
```

Why a virtual environment? It isolates all project dependencies from your global
Python installation. This means different projects can use different library
versions without conflicts. It is standard practice for any Python project.

### Step 2 — Activate it
```bash
# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Set your API key
Create a `.env` file in the project root:
```
GROQ_API_KEY=gsk_your_key_here
```

Why `.env` and not hardcoding the key in the code? If you ever share your code
or push it to GitHub, a hardcoded key gets exposed and the provider revokes it
automatically. The `.env` file is listed in `.gitignore` so it never gets
committed. The `python-dotenv` library loads it into memory at runtime — the
key never appears in source code.

---

## Usage

### Default run (uses sample files included in project)
```bash
python main.py
```

### Custom input files
```bash
python main.py --inspection "path/to/report.pdf" --thermal "path/to/thermal.pdf"
```

### Custom output filename
```bash
python main.py --inspection "report.pdf" --thermal "thermal.pdf" --output "Client_DDR.docx"
```

### Help
```bash
python main.py --help
```

---

## How the Pipeline Works — Phase by Phase

The system is divided into 7 phases. Each phase has a dedicated file with a
single responsibility. This separation makes debugging, testing, and modifying
any one part easy without touching the rest.

---

### Phase 1 — Environment Setup

Before writing any code, the environment was set up properly:
- Python 3.13 confirmed on the system
- Virtual environment created with `python -m venv venv`
- All libraries installed inside the venv, not globally
- `.env` file created for API key storage
- `.gitignore` created to protect `.env` and `venv/`

This phase also involved a significant challenge with the LLM provider — covered
in detail in the "Why Groq Instead of Gemini" section below.

---

### Phase 2 — Library Selection

Every library was chosen deliberately. Here is the reasoning for each:

**PyMuPDF (fitz)**
Used for extracting embedded images from PDFs. This was the most critical
library choice. PyPDF2 and pdfplumber both failed to extract images — they only
handle text. PyMuPDF is the only Python library that reliably extracts actual
embedded image bytes from PDF files. It also handles the `largest_only` strategy
(explained in Phase 3) which was needed to avoid extracting thousands of tiny
image fragments.

Why not Camelot? Camelot is only for table extraction, not images.
Why not pdfminer? Too low-level, no image support, verbose API.

**pdfplumber**
Used for layout-aware text extraction from the inspection report. It preserves
the spatial positioning of text on the page better than PyPDF2, which matters
when parsing structured sections like "Impacted Area 1", "Negative side
Description", etc.

Why not PyPDF2 for inspection text? PyPDF2 sometimes merges text from different
columns incorrectly. pdfplumber handles multi-column layouts better.

**PyPDF2**
Used specifically for the thermal PDF text extraction. The thermal PDF encodes
its text in UTF-16 (each character has a null byte between it, like
`\x00H\x00o\x00t\x00s\x00p\x00o\x00t`). PyPDF2 handles this encoding and
allows us to strip the null bytes with `.replace("\x00", "")`. pdfplumber
returned empty strings for the thermal pages because it could not decode this
encoding.

This was discovered during Phase 3 testing when thermal records showed
`hotspot: None` despite the data clearly being in the PDF.

**Groq (llama-3.3-70b-versatile)**
The LLM used for generating the DDR text. Chosen after Google Gemini failed
completely — full story in the "Why Groq Instead of Gemini" section.

**python-docx**
Used for generating the final Word document. Chosen over PDF generation because:
- Images embed inline with text naturally and reliably
- Clients can open, read, and edit it in Microsoft Word
- Converting to PDF is a one-click operation in Word
- python-docx has a clean API for tables, headings, images, and formatting
- Generating PDFs programmatically with embedded images requires ReportLab,
  which has a steep learning curve and complex layout management

**Pillow (PIL)**
Required by python-docx internally for image format detection and processing.
Not called directly in our code but must be installed.

**python-dotenv**
Loads the `.env` file into `os.environ` at runtime. Industry standard approach
for keeping secrets out of source code.

---

### Phase 3 — PDF Data Extraction (`extractor.py`)

This phase extracts three things from the two PDFs:

**1. Inspection report text**
Extracted page by page using pdfplumber. Each page's text is stored separately
and also concatenated into a single `full_text` string. The summary table
section is isolated by searching for the "SUMMARY TABLE" heading and grabbing
the next 3000 characters.

**2. Thermal temperature data**
Each page of the thermal PDF contains one thermal scan with metadata:
hotspot temperature, coldspot temperature, emissivity, date, and source image
filename. This is extracted using PyPDF2 with regex patterns after stripping
UTF-16 null bytes.

**3. Embedded images**
Images are extracted using PyMuPDF with two different strategies:

For the inspection report: `largest_only=False` — extract all images because
each page of the photo appendix (pages 11-23) contains multiple site photos
that are all needed.

For the thermal report: `largest_only=True` — extract only the largest image
per page. This was critical. The thermal PDF internally stores each thermal
scan as dozens of tiny image fragments (the PDF had 5400 image objects when
extracting all). By selecting only the largest image per page, we get exactly
30 clean thermal scans — one per page.

**Challenge encountered:** The first extraction attempt returned 5400 thermal
images. Debugging revealed the thermal PDF stores each scan as many small
overlapping image tiles. The `largest_only` strategy solved this cleanly.

**Challenge encountered:** Inspection images were initially filtered with
`"page1" not in path` to skip early pages, but this accidentally excluded
`page10`, `page11`, `page12` etc. Fixed by extracting the page number as an
integer and checking `page_num >= 11`.

All extracted images are saved to `temp_images/` with clear naming:
`inspection_page{N}_img{M}.jpeg` and `thermal_page{N}.jpeg`.

---

### Phase 4 — Data Structuring (`structurer.py`)

Raw extracted text is not ready for an AI prompt. This phase transforms it into
clean, labeled sections. Think of Phase 3 as getting raw ingredients and Phase 4
as prepping them before cooking.

**Property info** — Parsed from page 1 using regex patterns for each field
(inspection date, inspected by, property type, floors, score, etc.).

**Impacted areas** — The inspection report lists 7 impacted areas, each with a
"Negative side Description" (problem observed) and "Positive side Description"
(source/cause location). These are extracted by splitting the text on
"Impacted Area N" markers and then using regex to find each description block.

**Challenge encountered:** The regex for area descriptions was initially cutting
descriptions too short — Area 5 returned just "Issue" instead of "External wall
crack and Duct Issue", and Area 7 returned "Positive side photographs" instead
of the actual description. Fixed by adding `Photo \d` as a stop pattern to
prevent the regex from capturing photo reference lists, and by stripping
trailing photo references with a cleanup regex.

**Summary table** — The PDF summary table has layout artifacts from extraction
(extra spaces in words like "dampne ss", flat numbers like "103" mixed into
point numbers). Regex parsing was attempted but proved brittle. The decision was
made to pass the raw summary text directly to the AI and let it parse it
intelligently — the AI handles messy text far better than regex.

**Checklist** — Key checklist fields (leakage timing, concealed plumbing, tile
gaps, structural condition) are extracted with specific regex patterns. Fields
that could not be reliably extracted (external wall cracks, algae/fungus) are
left as "Not Available" and the AI fills them from context.

**Thermal summary** — All 30 thermal records are formatted into a clean text
block. Readings at or above 27°C hotspot are flagged as `[HIGH]` to signal
active moisture zones to the AI.

**Thermal-to-area mapping** — 30 thermal scans are distributed evenly across
7 inspection areas (approximately 4 scans per area). This mapping is used in
the Word document to place thermal images under their corresponding area sections.

---

### Phase 5 — AI Prompt Engineering (`prompt_builder.py` + `ai_generator.py`)

**Why split into two files?**
Prompt tuning is frequent during development. If the AI output quality is poor,
you only need to edit `prompt_builder.py`. You never need to touch the API code
in `ai_generator.py`. This separation also makes it easy to test the prompt
content without making API calls.

**Prompt design strategy:**
The prompt is structured in layers:

1. Role definition — "You are an expert property inspection report writer"
2. Strict rules — do not invent facts, write "Not Available" for missing data,
   flag conflicts, use client-friendly language
3. All input data — property info, impacted areas, summary table, checklist,
   thermal summary — each clearly labeled as INPUT DATA
4. Thermal interpretation guide — explains what hotspot/coldspot differences
   mean, what [HIGH] flags indicate, what emissivity 0.94 means
5. Output instructions — exact section headings to use, what to write in each,
   wrapped in `---DDR START---` and `---DDR END---` markers for reliable parsing

**Why low temperature (0.3)?**
Temperature controls how creative vs. factual the model is. For a diagnostic
report, we want factual and precise output, not creative writing. 0.3 keeps the
model grounded in the provided data.

**Why 4096 max tokens?**
A full 7-section DDR with detailed area observations needs room. 4096 tokens
gives enough space for a thorough report without hitting limits.

**Section parsing:**
The AI response is parsed by splitting on `## ` headings and matching each
section heading to a dict key. The `---DDR START---` / `---DDR END---` markers
ensure we only parse the actual report content, not any preamble the model adds.

**Result:** ~2119 input tokens, ~1700 output tokens, total ~3800 tokens per run.
All 7 sections filled consistently.

---

### Phase 6 — Report Generation (`report_generator.py`)

The Word document is built section by section using python-docx.

**Cover page** — Contains the report title, subtitle, and a 2-column table with
all 8 property info fields. Bold labels in the left column, values in the right.

**AI text cleaning** — The LLM outputs markdown formatting (`**bold**`, `*italic*`,
`## headings`). These are stripped before writing to Word since Word has its own
formatting system. The `clean_ai_text()` function handles this with regex.

**Image embedding strategy:**
- Inspection photos: filtered to pages 11-23 (photo appendix), skipping the
  repeated 26145-byte header PNG that appears on every page, and skipping
  anything under 5KB (PDF artifacts). First 12 qualifying photos are embedded.
- Thermal images: 2 scans per area, placed under each area's thermal scan
  heading with a caption showing filename, hotspot, and coldspot temperatures.

**Challenge encountered:** Images were showing as filenames in the document
instead of actual embedded images. Debugging revealed the issue was with path
resolution — `os.path.join(os.getcwd(), relative_path)` was doubling the path
when the relative path already started with `temp_images\`. Fixed by using
`os.path.abspath()` which correctly resolves any relative path to absolute
regardless of its current form.

**Challenge encountered:** The `add_image_safe` function was silently catching
exceptions without printing them. Added explicit error printing to expose the
actual failure during debugging.

**Output format:** `.docx` was chosen over PDF because:
- python-docx handles image embedding cleanly
- Clients can open and edit in Microsoft Word
- One-click PDF conversion is available in Word
- ReportLab (for PDF generation) has complex layout management

---

### Phase 7 — Integration and Testing (`main.py`)

`main.py` is the single entry point that wires all phases together. It provides:

- CLI argument parsing with `argparse` — supports `--inspection`, `--thermal`,
  `--output` flags with sensible defaults
- Input validation before the pipeline starts — checks both PDFs exist and the
  API key is set, exits cleanly with error messages if not
- Step-by-step progress logging — shows `[1/5]`, `[2/5]` etc. so the user
  knows what is happening during the ~90 second run
- Timing — reports total elapsed time at the end
- Error handling — catches exceptions, prints the traceback, exits with code 1
- KeyboardInterrupt handling — exits cleanly if the user presses Ctrl+C

---

## DDR Output Structure

The generated report contains:

| Section | Content |
|---|---|
| Cover Page | Property details table with all 8 fields |
| 1. Property Issue Summary | 3-5 sentence executive overview |
| 2. Area-Wise Observations | Per-area problems, sources, thermal data, severity + photos |
| 3. Probable Root Cause | AI-reasoned root cause linking inspection + thermal data |
| 4. Severity Assessment | Overall rating (Low/Moderate/High) + top 3 critical issues |
| 5. Recommended Actions | Prioritized action list with location and reason |
| 6. Additional Notes | Conflicts, extra observations |
| 7. Missing or Unclear Information | Explicitly flags gaps in source data |

---

## Why Groq Instead of Google Gemini — Full Story

### Original Plan

The initial design chose Google Gemini as the LLM for strong reasons:
- Free tier available via Google AI Studio
- Native multimodal support (text + images in the same API call)
- 1 million token context window
- Fast inference

### What Actually Happened

**Problem 1 — Deprecated SDK**
The `google-generativeai` package was installed first. It immediately showed:
`"All support for the google.generativeai package has ended. Switch to google-genai."`
Switched to the new `google-genai` SDK.

**Problem 2 — Zero quota on all models**
Every API call returned:
`429 RESOURCE_EXHAUSTED — limit: 0, model: gemini-2.0-flash`
This was not a rate limit (which would say "retry in X seconds with remaining
quota"). `limit: 0` means the project has zero quota allocated — it cannot make
any calls at all.

Tried every available model: gemini-2.0-flash, gemini-2.0-flash-lite,
gemini-1.5-flash. All returned `limit: 0`.

**Problem 3 — Multiple API keys, same result**
Two existing API keys were tried. Both were under "Default Gemini Project" and
both returned the same error. The quota is per-project, not per-key.

**Problem 4 — New project did not help**
Created a fresh Google Cloud project named "DDRGenAI" with a brand new API key.
Same `limit: 0` error. Even after explicitly enabling the Generative Language
API on Google Cloud Console (it showed "Enable" — meaning it was not enabled),
the error persisted after enabling it.

**Root Cause**
The Gemini API free tier is geo-restricted in India. Google does not provide
free tier `generate_content` quota to accounts in certain regions. The API
connection works (model listing succeeds), but actual generation calls are
blocked at the quota level. Attaching a billing account to the Google Cloud
project would unlock it, but that requires a credit card.

**Decision**
Rather than require billing setup, switched to Groq which is genuinely free
with no geo-restrictions.

### Why Groq

- Completely free — no billing, no credit card, no geo-restrictions
- Works in India without any workarounds
- Fast inference via custom LPU (Language Processing Unit) hardware
- `llama-3.3-70b-versatile` is a strong model for structured report generation
- Clean, simple Python SDK
- Connected and responded successfully on the first attempt

### The Multimodal Trade-off

Gemini's main advantage was multimodal — sending images directly in the API
call. Groq's free tier does not support image input.

This was handled by passing thermal data as structured text instead of images:
```
Scan 01 | RB02380X.JPG | Hotspot: 28.8 °C [HIGH] | Coldspot: 23.4 °C | Date: 27/09/22
```

This is actually more reliable than sending raw images because:
- The AI gets precise numerical data it can reason about directly
- No image encoding/decoding overhead
- Token-efficient — 30 scans fit in ~500 tokens
- The actual thermal scan images are still embedded in the Word output

Inspection photos are embedded directly in the Word document under their
relevant sections, so the client sees all visual evidence in the final report.

---

## Challenges and How They Were Solved

| Challenge | Root Cause | Solution |
|---|---|---|
| Gemini API returning limit: 0 | Geo-restriction in India | Switched to Groq |
| google-generativeai deprecated | Google migrated to new SDK | Switched to google-genai, then removed entirely |
| Thermal PDF returning 5400 images | PDF stores scans as many tiny tiles | largest_only=True strategy in PyMuPDF |
| Thermal text returning None | UTF-16 encoding with null bytes | PyPDF2 + .replace("\x00", "") |
| pdfplumber returning empty for thermal | Cannot decode UTF-16 thermal text | Used PyPDF2 specifically for thermal PDF |
| Area descriptions cut too short | Regex stopping at wrong boundary | Added Photo \d as stop pattern + cleanup regex |
| Summary table regex catching flat numbers | "103" matched as point number | Limited regex to 1-2 digit numbers only |
| Images showing as filenames in Word | os.path.join doubling relative paths | Switched to os.path.abspath() |
| Windows terminal encoding errors | Degree symbol and Unicode chars | Display-only issue, data is correct in .docx |
| Image filter excluding page10+ | String "page1" matched page10, page11 | Extract page number as integer, check >= 11 |

---

## Design Decisions

**Why not LangChain?**
LangChain adds abstraction layers that make debugging harder. For a
single-pipeline task like this, plain Python is cleaner, easier to understand,
and easier to modify. Every step is explicit and traceable.

**Why not a local LLM (Ollama/LLaMA)?**
Local models capable of structured report generation (7B+ parameters) require
significant RAM and GPU. They are slower, harder to set up, and produce lower
quality structured output than hosted models. For a free, reliable solution,
a hosted API is the right choice.

**Why not output PDF directly?**
Generating PDFs with embedded images programmatically requires ReportLab, which
has complex layout management. Word documents are easier to generate, easier for
clients to read and edit, and can be converted to PDF with one click.

**Why separate prompt_builder.py from ai_generator.py?**
Prompt quality directly affects report quality. During development, the prompt
was tuned multiple times. Keeping it in a separate file means you never risk
accidentally breaking the API connection code while editing the prompt, and you
can test prompt output by printing it without making any API calls.

**Why pass summary table raw text to AI instead of parsing it?**
The PDF extraction produces artifacts — extra spaces in words, flat numbers
mixed into point numbers, inconsistent spacing. Regex parsing of this messy text
was brittle and kept breaking. The AI handles natural language text with
imperfections far better than regex. The raw summary text is passed directly and
the AI extracts the observations correctly every time.

**Why temperature=0.3 for the LLM?**
Lower temperature = more deterministic, factual output. Higher temperature =
more creative, varied output. A diagnostic report must be factual and grounded
in the provided data. 0.3 keeps the model from inventing details while still
allowing it to write fluent, well-structured sentences.

---

## Generalisation

The system is designed to work on similar inspection reports, not just the
sample files. The extraction and structuring logic looks for structural patterns
("Impacted Area N", "Negative side Description", "Hotspot :", etc.) that are
common to this class of inspection report. The AI prompt explicitly instructs
the model to handle missing or conflicting information gracefully.

For a different report format, the regex patterns in `structurer.py` and the
extraction logic in `extractor.py` would need to be adjusted to match the new
document structure.

---

## Post-Build Improvements

After the initial build was complete and tested, several issues were identified
and fixed. Each one is documented here with the original problem, why it was
wrong, and what was changed.

---

### Improvement 1 — Web UI Added (Flask)

**What was built initially:**
The system ran entirely from the command line via `main.py`. There was no way
for a non-technical user to interact with it without running Python commands.

**Why that was not appropriate:**
The assignment requires a live link that anyone can click and use directly.
A CLI tool cannot be shared as a link. Users would need Python installed,
dependencies set up, and knowledge of terminal commands — none of which is
realistic for a client or evaluator.

**What was changed:**
Built a full web interface using Flask with three pages:
- Upload page (`/`) — user uploads both PDFs and clicks Generate
- Processing page (`/processing/<job_id>`) — shows live progress with a spinner
  and step-by-step status updates polled every 2 seconds via JavaScript
- Report viewer page (`/report/<job_id>`) — displays the full DDR text in a
  clean formatted layout with download button

The pipeline runs in a background thread so the browser does not time out
during the ~90 second generation process. Each upload gets a unique job ID
(UUID) so multiple users can run simultaneously without conflicts.

---

### Improvement 2 — PDF Validation Before Processing

**What was built initially:**
Any uploaded file was accepted and sent directly into the pipeline. If a user
uploaded the wrong type of PDF (a random document, a resume, a blank file),
the pipeline would either crash mid-way or produce a meaningless report.

**Why that was not appropriate:**
A crash mid-pipeline wastes time, consumes API tokens, and gives the user a
confusing error message deep in the stack trace. The system should fail fast
with a clear, helpful message before any processing begins.

**What was changed:**
Built `validator.py` which checks both uploaded PDFs before the pipeline starts:

For the inspection PDF — checks for structural markers the model depends on:
`inspection`, `impacted area`, `negative side`, `positive side`. If more than
one required keyword is missing, the file is rejected with a specific message
explaining what was expected.

For the thermal PDF — checks for thermal scan markers: `hotspot`, `coldspot`,
`emissivity`. Uses PyPDF2 directly because the thermal PDF uses UTF-16 encoding
that pdfplumber cannot read.

Also detects swapped files — if the user uploads the thermal PDF in the
inspection slot and vice versa, it catches this and tells them to swap.

Rejected files are deleted immediately and the user is returned to the upload
page with a clear error message. No API calls are made, no pipeline runs.

---

### Improvement 3 — Thermal Images Were All Identical

**What was built initially:**
The thermal image extraction used `largest_only=True` — for each page of the
thermal PDF, PyMuPDF extracted the image with the largest file size. This was
intended to get the main thermal scan and skip tiny icon/UI fragments.

**Why that was not appropriate:**
The thermal PDF uses a PDF optimization technique called xref sharing — all
image objects are stored once globally in the PDF and every page references the
same pool. When PyMuPDF's `get_images()` is called per page, it returns the
same shared image list for every page. The largest image happened to be a
79,254-byte background graphic (xref=245) that appeared on one page but was
referenced globally. This same image was extracted for all 30 pages, making
every thermal scan look identical despite having different filenames and
temperature data.

**How it was discovered:**
After generating the first report, all 30 thermal images in the Word document
were visually identical. Debugging showed all extracted files were exactly
79,254 bytes. Further investigation with PyMuPDF confirmed all pages returned
the same xref list — the PDF shares image objects across pages.

**What was changed:**
Switched from image extraction to page rendering. Instead of extracting embedded
image bytes, PyMuPDF now renders each page directly to a PNG using
`page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))`. This renders what is actually
visible on that specific page — the correct thermal scan for that page — at 2x
zoom for good resolution. The resulting 30 PNG files are all different sizes
(791KB to 887KB) confirming each is a unique render of its page.

---

### Improvement 4 — Report Format Was Confusing (Images Separated From Context)

**What was built initially:**
Section 2 (Area-Wise Observations) was structured as three separate blocks:

```
Block 1: All area text (Areas 1 through 7, all together)
Block 2: All inspection photos (Photos 1-64, all dumped together)
Block 3: All thermal scans (Scans 1-30, all grouped by area but separate)
```

**Why that was not appropriate:**
A reader looking at Area 1 (Hall dampness) had to scroll past all 7 areas of
text, then scroll through dozens of photos with no labels, then find the thermal
scans for Area 1 at the bottom. There was no visual connection between the
written observation, the site photograph showing the problem, and the thermal
scan confirming moisture. This defeats the purpose of a diagnostic report —
the reader cannot easily correlate the finding with its evidence.

**What was changed:**
Rewrote `write_section_2` in `report_generator.py` to follow a per-area
interleaved structure:

```
Area 1
  → Observation text (problem + source/cause + severity)
  → Inspection Photographs (Photos 1-7, the actual site photos for Area 1)
  → Thermal Scan Data (2 thermal scans mapped to Area 1)

Area 2
  → Observation text
  → Inspection Photographs (Photos 8-14)
  → Thermal Scan Data (2 scans for Area 2)

... and so on for all 7 areas
```

The photo-to-area mapping was derived from the inspection report's own summary
table which lists which photo numbers belong to which area:
- Area 1 (Hall): Photos 1-7
- Area 2 (Bedroom): Photos 8-14
- Area 3 (Master Bedroom): Photos 15-30
- Area 4 (Kitchen): Photos 31-37
- Area 5 (Master Bedroom Wall): Photos 38-48
- Area 6 (Parking): Photos 49-57
- Area 7 (Common Bathroom): Photos 58-64

The AI-generated text is also split per area by parsing the numbered area
headings in the LLM output, so each area's text block appears directly above
its own photos and thermal scans.

This makes the report self-contained per area — a reader can look at Area 3,
read the observation, see the site photos showing the dampness, and immediately
see the thermal scan confirming the moisture zone, all without scrolling away.

---

### Improvement 5 — Web Report View Has No Images (By Design)

**What was built initially:**
The web report viewer showed only text. Images were not displayed in the browser.

**Why this is acceptable:**
Serving 150+ extracted images through a web server would require storing them
in a publicly accessible static folder, managing file paths per session, and
handling image serving routes — significant added complexity. The Word document
already contains all images correctly placed. The web view is intended as a
quick text preview, not a replacement for the full report.

**What was added:**
A bold amber notice bar at the top of the report page:

> Note: This web view displays the text report only. To view the full report
> with all inspection photographs and thermal scan images placed under their
> respective observations, please download the Word document (.docx).

This sets clear expectations for the user and directs them to the download
immediately.

---

## Deployment — Getting a Permanent Public URL

The local Flask server (`http://127.0.0.1:5000`) only works on your own machine
while the script is running. To get a permanent URL that anyone can access
anytime, the app is deployed to Railway.

### Why Railway (and not Render)

The app was first deployed on Render (free tier). It failed with:
`Worker (pid:57) was sent SIGKILL! Perhaps out of memory?`

Render's free tier provides 512MB RAM. PyMuPDF alone uses ~300MB when processing
PDFs, and the full pipeline (extraction + structuring + AI + Word generation)
exceeds the limit. The worker gets killed mid-run.

Railway was chosen as the replacement because:
- Free tier provides ~1GB RAM — enough for the full pipeline
- Deploys directly from GitHub, same as Render
- Auto-detects Python and uses the Procfile
- Gives a permanent public URL instantly
- $5 free credit per month covers light usage
- Why not Heroku: free tier was removed in 2022
- Why not Vercel: Python backend support is limited, not suited for long-running processes

---

### Deployment Steps

**1. Push code to GitHub**

```bash
git init
git add .
git commit -m "Initial commit - DDRGen AI complete"
git remote add origin https://github.com/YOUR_USERNAME/ddrgen-ai.git
git push -u origin main
```

The `.gitignore` protects `.env`, `venv/`, `uploads/`, `outputs/`, and
`temp_images/` — none of these are pushed to GitHub.

**2. Deploy on Railway**

- Go to https://railway.app and sign up with GitHub
- Click New Project → Deploy from GitHub repo
- Select your `ddrgen-ai` repository
- Click Variables tab → Add Variable:
  - Key: `GROQ_API_KEY` — Value: your `gsk_...` key
- Click Settings → Networking → Generate Domain
- Select region: Asia Pacific (Singapore) for best performance from India

Railway auto-detects Python, installs from `requirements.txt`, and starts the
app using the `Procfile`. Permanent URL is ready in 2-3 minutes.

---

### Why the Start Command Uses Extra Flags

The Procfile contains: `gunicorn app:app --timeout 120 --workers 1`

`--timeout 120`
The DDR pipeline takes approximately 90 seconds (PDF extraction + AI generation
+ Word document creation). Gunicorn's default timeout is 30 seconds. Without
this flag, the server kills the request mid-pipeline and the user gets a 502
error. 120 seconds gives enough headroom for the full pipeline to complete.

`--workers 1`
Each gunicorn worker loads the full pipeline into memory independently. Multiple
workers would exhaust RAM and crash the service. One worker handles requests
sequentially which is appropriate for this use case.

---

### Important Note on Free Tier Behaviour

Railway's free tier may spin down after periods of inactivity. The first request
after an idle period takes approximately 30 seconds to wake up. Subsequent
requests are instant. This is expected behaviour on the free plan.
