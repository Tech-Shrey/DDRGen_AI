"""
ai_generator.py
---------------
Sends the assembled prompt to Groq LLM and returns the DDR text.

Model: llama-3.3-70b-versatile
  - Strong reasoning and structured output
  - Large context window (128k tokens)
  - Fast inference via Groq's LPU hardware
  - Free tier, no geo-restrictions
"""

import os
from dotenv import load_dotenv
from groq import Groq


def generate_ddr(prompt: str) -> str:
    """
    Send prompt to Groq and return the generated DDR text.
    Handles API errors gracefully.
    """
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")

    client = Groq(api_key=api_key)

    print("Sending prompt to Groq LLM...")
    print(f"Model  : llama-3.3-70b-versatile")
    print(f"Tokens : ~{len(prompt)//4} input tokens")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert property inspection report writer. "
                        "You generate clear, accurate, client-friendly Detailed Diagnostic Reports (DDR). "
                        "You follow instructions precisely and never invent facts."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,      # low temperature = more factual, less creative
            max_tokens=4096,      # enough for a full detailed report
        )

        ddr_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens

        print(f"Response received. Total tokens used: {tokens_used}")
        return ddr_text

    except Exception as e:
        print(f"ERROR calling Groq API: {e}")
        raise


def extract_ddr_sections(ddr_text: str) -> dict:
    """
    Parse the LLM output into individual DDR sections.
    Looks for the ## headings defined in the prompt.
    Returns a dict with section names as keys.
    """
    import re

    sections = {
        "property_issue_summary":       "",
        "area_wise_observations":       "",
        "probable_root_cause":          "",
        "severity_assessment":          "",
        "recommended_actions":          "",
        "additional_notes":             "",
        "missing_unclear_information":  "",
        "full_text":                    ddr_text,
    }

    # Extract content between ---DDR START--- and ---DDR END---
    ddr_match = re.search(r"---DDR START---(.*?)---DDR END---", ddr_text, re.DOTALL)
    if ddr_match:
        ddr_body = ddr_match.group(1)
    else:
        ddr_body = ddr_text  # fallback: use full text

    # Map section headings to dict keys
    heading_map = {
        "1. PROPERTY ISSUE SUMMARY":        "property_issue_summary",
        "2. AREA-WISE OBSERVATIONS":        "area_wise_observations",
        "3. PROBABLE ROOT CAUSE":           "probable_root_cause",
        "4. SEVERITY ASSESSMENT":           "severity_assessment",
        "5. RECOMMENDED ACTIONS":           "recommended_actions",
        "6. ADDITIONAL NOTES":              "additional_notes",
        "7. MISSING OR UNCLEAR INFORMATION":"missing_unclear_information",
    }

    # Split by ## headings
    parts = re.split(r"##\s+", ddr_body)

    for part in parts:
        for heading, key in heading_map.items():
            if part.strip().startswith(heading):
                # Content is everything after the heading line
                content = part[len(heading):].strip()
                sections[key] = content
                break

    return sections


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from extractor import extract_all
    from structurer import structure_all
    from prompt_builder import build_prompt

    extracted  = extract_all("Sample Report.pdf", "Thermal Images.pdf")
    structured = structure_all(extracted)
    prompt     = build_prompt(structured)

    # Generate DDR
    ddr_text = generate_ddr(prompt)

    # Parse into sections
    sections = extract_ddr_sections(ddr_text)

    print("\n" + "="*60)
    print("DDR GENERATED SUCCESSFULLY")
    print("="*60)

    for key, content in sections.items():
        if key == "full_text":
            continue
        print(f"\n[{key.upper()}]")
        print(content[:300] if content else "-- empty --")
        print("...")
