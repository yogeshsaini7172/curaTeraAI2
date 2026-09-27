import os
import json
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

FILE_PATH = Path(__file__).parent / "data" / "processed" / "scheme_full.json"
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

def is_devanagari(text):
    return bool(re.search(r'[\u0900-\u097F]', text or ''))

def translate_scheme(doc):
    scheme_name = doc.get("scheme_name", "")
    authority = doc.get("implementing_authority", "")
    sections = doc.get("sections", {})
    
    benefits = sections.get("benefits", [])
    details = sections.get("details", [])
    eligibility = sections.get("eligibility", [])
    docs = sections.get("documents_required", [])
    process = sections.get("application_process", [])

    payload = {
        "scheme_name": scheme_name,
        "implementing_authority": authority,
        "benefits": benefits,
        "details": details,
        "eligibility": eligibility,
        "documents_required": docs,
        "application_process": process
    }

    prompt = f"""You are a professional Hindi translator for Indian Government Schemes.
Translate the following scheme details into clear, natural, official Hindi.
Return ONLY a valid JSON object with the exact same structure but keys with '_hi' suffix:
{{
  "scheme_name_hi": "...",
  "implementing_authority_hi": "...",
  "benefits_hi": ["..."],
  "details_hi": ["..."],
  "eligibility_hi": ["..."],
  "documents_required_hi": ["..."],
  "application_process_hi": ["..."]
}}

Input JSON:
{json.dumps(payload, ensure_ascii=False)}
"""

    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=850,
                temperature=0.2
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "limit" in err_str.lower():
                print(f"  [Rate limit/OTPM wait] Sleeping 15s before retry (attempt {attempt + 1})...", flush=True)
                time.sleep(15)
            else:
                print(f"  [API Error] {e}", flush=True)
                if attempt == 3:
                    raise e
                time.sleep(3)
    return {}

def main():
    if not FILE_PATH.exists():
        print(f"File not found: {FILE_PATH}", flush=True)
        return
        
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total schemes in dataset: {len(data)}", flush=True)
    
    to_translate = []
    for idx, d in enumerate(data):
        sec = d.get("sections", {})
        has_hindi = is_devanagari(d.get("scheme_name_hi", "")) and sec.get("eligibility_hi")
        
        # Check if translation was truncated in the previous run (due to slicing limits)
        is_truncated = len(sec.get("application_process", [])) > len(sec.get("application_process_hi", []))
        
        if not has_hindi or is_truncated:
            to_translate.append(idx)
            
    print(f"Schemes needing Hindi translation: {len(to_translate)}", flush=True)
    
    for count, idx in enumerate(to_translate, 1):
        doc = data[idx]
        scheme_id = doc.get("scheme_id")
        name = doc.get("scheme_name")
        print(f"[{count}/{len(to_translate)}] Translating {scheme_id}: {name[:45]}...", flush=True)
        
        try:
            res = translate_scheme(doc)
            if res and res.get("scheme_name_hi"):
                doc["scheme_name_hi"] = res.get("scheme_name_hi", doc.get("scheme_name", ""))
                doc["implementing_authority_hi"] = res.get("implementing_authority_hi", doc.get("implementing_authority", ""))
                
                if "sections" not in doc or not isinstance(doc["sections"], dict):
                    doc["sections"] = {}
                    
                doc["sections"]["benefits_hi"] = res.get("benefits_hi", [])
                doc["sections"]["details_hi"] = res.get("details_hi", [])
                doc["sections"]["eligibility_hi"] = res.get("eligibility_hi", [])
                doc["sections"]["documents_required_hi"] = res.get("documents_required_hi", [])
                doc["sections"]["application_process_hi"] = res.get("application_process_hi", [])
                
                # Save immediately to disk
                with open(FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"  ✓ {scheme_id} saved: {doc['scheme_name_hi'][:40]}", flush=True)
            else:
                print(f"  ✗ {scheme_id} returned empty translation", flush=True)
                
            time.sleep(2.5) # Safe gap between requests
        except Exception as e:
            print(f"Error translating {scheme_id}: {e}", flush=True)
            time.sleep(5)
            
    print("\nSUCCESS: All schemes translated and saved to scheme_full.json!", flush=True)

if __name__ == "__main__":
    main()
