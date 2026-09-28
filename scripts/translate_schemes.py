import os
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load environment
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

SCHEMES_PATH = BASE_DIR / "data" / "processed" / "scheme_full.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "scheme_translations_hi.json"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def clean_text_list(items, max_len=None):
    if not items:
        return []
    if isinstance(items, str):
        items = [items]
    res = []
    for it in items:
        s = str(it).strip()
        if re.match(r'^\[?svg\]?(\(.*\))?$', s, re.I) or s.lower() == 'svg':
            continue
        s = s.replace('***', '').replace('**', '').replace('\\*', '').replace('\ufeff', '').strip()
        if s.startswith('- '):
            s = s[2:].strip()
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
        if s and s.lower() != 'svg':
            res.append(s)
    if max_len:
        return res[:max_len]
    return res

def extract_scheme_fields(doc):
    scheme_name = doc.get("scheme_name", "Government Scheme")
    sections = doc.get("sections", {})
    
    benefit_en = "Financial & Technical Assistance under Government Guidelines."
    why_eligible_en = "Open to eligible citizens meeting prescribed scheme norms."
    required_docs = ["Aadhaar Card", "Bank Passbook", "Passport Size Photos"]
    description_en = ""
    application_process = []

    if isinstance(sections, dict):
        b_list = sections.get("benefits", [])
        if b_list and isinstance(b_list, list):
            benefit_en = " ".join(str(b) for b in b_list[:2])[:200]
        elif isinstance(b_list, str):
            benefit_en = b_list[:200]

        e_list = sections.get("eligibility", [])
        if e_list and isinstance(e_list, list):
            why_eligible_en = " ".join(str(e) for e in e_list[:2])[:150]
        elif isinstance(e_list, str):
            why_eligible_en = e_list[:150]

        d_list = sections.get("documents_required", [])
        clean_d = clean_text_list(d_list, max_len=6)
        if clean_d:
            required_docs = clean_d

        det_list = sections.get("details", [])
        if det_list and isinstance(det_list, list):
            description_en = " ".join(str(d) for d in det_list[:2])[:300]

        app_list = sections.get("application_process", [])
        clean_app = clean_text_list(app_list, max_len=6)
        if clean_app:
            application_process = clean_app

    return {
        "title": scheme_name,
        "benefit": benefit_en,
        "eligibility": why_eligible_en,
        "description": description_en or scheme_name,
        "required_docs": required_docs,
        "application_process": application_process
    }

def translate_scheme(fields):
    prompt = f"""You are a professional Hindi translator for Indian Government welfare schemes.
Translate the following scheme details into clear, natural, everyday Hindi suitable for Indian citizens.
Do not use overly complex Sanskritized words; use simple and standard Hindi.
Keep terms like 'Aadhaar Card', 'Portal', 'OTP', 'Online', 'Offline', 'SMS' easily recognizable in Hindi.

Return ONLY a valid JSON object matching this structure:
{{
  "titleHi": "हिंदी में योजना का नाम",
  "benefitHi": "हिंदी में लाभ का विवरण",
  "whyEligibleHi": "हिंदी में संक्षिप्त पात्रता",
  "descriptionHi": "हिंदी में विवरण",
  "requiredDocsHi": ["दस्तावेज़ 1", "दस्तावेज़ 2"],
  "applicationProcessHi": ["स्टेप 1...", "स्टेप 2..."]
}}

Input Scheme Data:
Title: {fields['title']}
Benefit: {fields['benefit']}
Eligibility: {fields['eligibility']}
Description: {fields['description']}
Required Documents: {json.dumps(fields['required_docs'], ensure_ascii=False)}
Application Process: {json.dumps(fields['application_process'], ensure_ascii=False)}
"""

    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=800
    )
    content = response.choices[0].message.content
    return json.loads(content)

def main():
    if not SCHEMES_PATH.exists():
        print(f"Error: {SCHEMES_PATH} does not exist.")
        return

    with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
        schemes = json.load(f)

    # Load existing translations if any
    translations = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                translations = json.load(f)
        except Exception:
            translations = {}

    total = len(schemes)
    print(f"Total schemes to translate: {total}. Already translated: {len(translations)}")

    for idx, s in enumerate(schemes, 1):
        s_id = s.get("scheme_id")
        if s_id in translations:
            print(f"[{idx}/{total}] Already translated {s_id}, skipping.")
            continue

        print(f"[{idx}/{total}] Translating {s_id}: {s.get('scheme_name')[:40]}...")
        try:
            fields = extract_scheme_fields(s)
            hi_data = translate_scheme(fields)
            translations[s_id] = hi_data

            # Save progress incrementally
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            time.sleep(0.5)  # respectful pause to avoid rate limits
        except Exception as e:
            print(f"Error translating {s_id}: {e}")
            time.sleep(2)

    print(f"\nAll {total} schemes processed! Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
