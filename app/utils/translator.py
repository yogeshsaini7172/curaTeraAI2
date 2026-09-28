import os
import json
import re
import threading
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / ".env")

OUTPUT_PATH = BASE_DIR / "data" / "processed" / "scheme_translations_hi.json"

_file_lock = threading.Lock()
_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            _client = Groq(api_key=api_key)
    return _client

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

def translate_single_scheme(doc):
    """
    Translates a single scheme into natural Hindi and stores it in scheme_translations_hi.json.
    """
    scheme_id = doc.get("scheme_id")
    if not scheme_id:
        return None

    client = get_client()
    if not client:
        print("[Translator] GROQ_API_KEY not configured, skipping auto-translation.")
        return None

    fields = extract_scheme_fields(doc)
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

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=800,
            timeout=25
        )
        content = response.choices[0].message.content
        hi_data = json.loads(content)

        with _file_lock:
            all_translations = {}
            if OUTPUT_PATH.exists():
                try:
                    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                        all_translations = json.load(f)
                except Exception:
                    all_translations = {}

            all_translations[scheme_id] = hi_data

            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(all_translations, f, ensure_ascii=False, indent=2)

        print(f"[Translator] Auto-translated {scheme_id} ({fields['title'][:30]}) successfully!")
        return hi_data
    except Exception as e:
        print(f"[Translator] Error auto-translating {scheme_id}: {e}")
        return None

_in_progress = set()

def ensure_scheme_translated_async(doc):
    """
    Spawns background translation for an untranslated scheme.
    """
    scheme_id = doc.get("scheme_id")
    if not scheme_id or scheme_id in _in_progress:
        return

    _in_progress.add(scheme_id)

    def _task():
        try:
            translate_single_scheme(doc)
        finally:
            _in_progress.discard(scheme_id)

    thread = threading.Thread(target=_task, daemon=True)
    thread.start()
