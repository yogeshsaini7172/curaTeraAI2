from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
import jwt
import os
import json
import uuid
import datetime
from pathlib import Path
import pypdf
import io
from dotenv import load_dotenv

from models.user import db, users_collection

load_dotenv()

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

SECRET_KEY = os.getenv("JWT_SECRET", "SUPER_SECRET_KEY")
schemes_collection = db["schemes"]

MOCK_SCHEMES_PATH = Path(__file__).parent / "mock_schemes.json"
POLICY_HISTORY_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "policy_history.json"
RAG_DOCS_PATH = Path(__file__).parent.parent.parent / "data" / "rag" / "rag_documents.json"

def verify_admin(req):
    """Verify Bearer token has role == 'admin'."""
    auth_header = req.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, "Authorization token is missing"
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get('role') != 'admin':
            return None, "Forbidden: Admin privileges required"
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except Exception as e:
        return None, f"Invalid token: {str(e)}"

def load_all_schemes():
    """Load combined schemes from MongoDB, mock_schemes.json and scheme_full.json."""
    schemes = []
    existing_ids = set()
    
    # 1. From MongoDB
    try:
        db_schemes = list(schemes_collection.find({}, {'_id': 0}))
        for s in db_schemes:
            schemes.append(s)
            if s.get('id'):
                existing_ids.add(s.get('id'))
    except Exception as e:
        print(f"Error fetching from MongoDB schemes: {e}")

    # 2. From mock_schemes.json for defaults (recently uploaded)
    if MOCK_SCHEMES_PATH.exists():
        try:
            with open(MOCK_SCHEMES_PATH, 'r', encoding='utf-8') as f:
                mock_list = json.load(f)
                for ms in mock_list:
                    if ms.get('id') not in existing_ids:
                        schemes.append(ms)
                        existing_ids.add(ms.get('id'))
        except Exception as e:
            print(f"Error reading mock_schemes.json: {e}")

    # 3. From scheme_full.json (Master dataset ~ 5000+ schemes)
    if FULL_SCHEMES_PATH.exists():
        try:
            from app.routes.schemes import format_retrieved_scheme
            with open(FULL_SCHEMES_PATH, 'r', encoding='utf-8') as f:
                full_list = json.load(f)
                for item in full_list:
                    sid = item.get('scheme_id') or item.get('id')
                    # Admin panel uses 'id' instead of 'scheme_id'
                    if sid and sid not in existing_ids:
                        formatted = format_retrieved_scheme(item)
                        # Add fullScheme for editing capabilities
                        formatted['fullScheme'] = item
                        schemes.append(formatted)
                        existing_ids.add(sid)
        except Exception as e:
            print(f"Error reading scheme_full.json: {e}")

    return schemes

FULL_SCHEMES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "scheme_full.json"

def sync_scheme_to_mock_file(scheme_data, is_new=True):
    """Sync newly saved scheme to mock_schemes.json so citizen endpoints pick it up."""
    if not MOCK_SCHEMES_PATH.exists():
        return
    try:
        with open(MOCK_SCHEMES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        target_id = scheme_data.get('id')
        found_idx = -1
        for idx, item in enumerate(data):
            if item.get('id') == target_id:
                found_idx = idx
                break
        
        if found_idx >= 0:
            data[found_idx] = scheme_data
        else:
            data.insert(0, scheme_data)

        with open(MOCK_SCHEMES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error syncing mock_schemes.json: {e}")

def sync_scheme_to_full_file(scheme_data, is_new=True):
    """Sync newly saved scheme to scheme_full.json (the master dataset used by mobile app & chatbot)."""
    if not FULL_SCHEMES_PATH.exists():
        print("scheme_full.json not found, skipping full sync.")
        return
    try:
        with open(FULL_SCHEMES_PATH, 'r', encoding='utf-8') as f:
            full_list = json.load(f)

        scheme_id = scheme_data.get('id', '')

        # Build scheme_full.json compatible entry
        full_entry = {
            "scheme_id": scheme_id,
            "scheme_name": scheme_data.get('titleEn', ''),
            "scheme_name_hi": scheme_data.get('titleHi', ''),
            "jurisdiction_type": "Central",
            "jurisdiction": "India",
            "implementing_authority": scheme_data.get('ministryEn', 'Government of India'),
            "implementing_authority_hi": scheme_data.get('ministryHi', 'भारत सरकार'),
            "source_file": "admin_pdf_upload",
            "source_start_line": 0,
            "sections": {
                "details": [scheme_data.get('descriptionEn', '')],
                "details_hi": [scheme_data.get('descriptionHi', '')],
                "benefits": [scheme_data.get('benefitEn', '')],
                "benefits_hi": [scheme_data.get('benefitHi', '')],
                "eligibility": [scheme_data.get('whyEligibleEn', '')],
                "eligibility_hi": [scheme_data.get('whyEligibleHi', '')],
                "application_process": scheme_data.get('applicationSteps') or [
                    scheme_data.get('applicationProcess', 'Visit nearest Common Service Centre (CSC) or apply online at the official portal.')
                ],
                "application_process_hi": scheme_data.get('applicationStepsHi') or [
                    scheme_data.get('applicationProcess', 'निकटतम कॉमन सर्विस सेंटर (CSC) पर जाएं या आधिकारिक पोर्टल पर ऑनलाइन आवेदन करें।')
                ],
                "documents_required": scheme_data.get('requiredDocsEn', []),
                "documents_required_hi": scheme_data.get('requiredDocsHi', []),
                "frequently_asked_questions": [],
                "sources_and_references": [scheme_data.get('officialUrl', 'https://myscheme.gov.in')],
                "exclusions": [],
            },
            "raw_text": f"{scheme_data.get('titleEn', '')}\n\n{scheme_data.get('descriptionEn', '')}\n\nBenefits: {scheme_data.get('benefitEn', '')}\n\nEligibility: {scheme_data.get('whyEligibleEn', '')}",
            "image_url": scheme_data.get('imageUrl', ''),
            # Keep admin panel fields for frontend rendering
            "titleEn": scheme_data.get('titleEn', ''),
            "titleHi": scheme_data.get('titleHi', ''),
            "category": scheme_data.get('category', 'general'),
            "benefitAmount": scheme_data.get('benefitAmount', ''),
            "officialUrl": scheme_data.get('officialUrl', 'https://myscheme.gov.in'),
            "helplinePhone": scheme_data.get('helplinePhone', ''),
            "themeColor": scheme_data.get('themeColor', '#1E3A8A'),
            "themeLight": scheme_data.get('themeLight', '#EFF6FF'),
            "criteria": scheme_data.get('criteria', {}),
            "updatedAt": scheme_data.get('updatedAt', ''),
            "createdAt": scheme_data.get('createdAt', ''),
        }

        # Check if already exists (edit) or insert new
        found_idx = -1
        for idx, item in enumerate(full_list):
            if item.get('scheme_id') == scheme_id or item.get('id') == scheme_id:
                found_idx = idx
                break

        if found_idx >= 0:
            full_list[found_idx] = full_entry
            print(f"Updated scheme '{scheme_id}' in scheme_full.json")
        else:
            full_list.insert(0, full_entry)
            print(f"Added new scheme '{scheme_id}' to scheme_full.json")

        with open(FULL_SCHEMES_PATH, 'w', encoding='utf-8') as f:
            json.dump(full_list, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Error syncing scheme_full.json: {e}")


def append_rag_document(scheme_data):
    """Add or update scheme in rag_documents.json so RAG chatbot knows about it."""
    if not RAG_DOCS_PATH.exists():
        return
    try:
        with open(RAG_DOCS_PATH, 'r', encoding='utf-8') as f:
            docs = json.load(f)

        scheme_id = scheme_data.get('id', 'unknown')
        scheme_name = scheme_data.get('titleEn', 'Unknown Scheme')
        
        # Remove previous chunks for this scheme if editing
        docs = [d for d in docs if d.get('scheme_id') != scheme_id]

        # Create structured text chunks
        new_chunk = {
            "scheme_id": scheme_id,
            "scheme_name": scheme_name,
            "section": "Overview & Benefits",
            "chunk_id": f"{scheme_id}_01",
            "text": f"Scheme Name: {scheme_name}\nMinistry: {scheme_data.get('ministryEn')}\nCategory: {scheme_data.get('category')}\nBenefits: {scheme_data.get('benefitEn')}\nBenefit Amount: {scheme_data.get('benefitAmount')}\nEligibility: {scheme_data.get('whyEligibleEn')}\nDescription: {scheme_data.get('descriptionEn')}\nRequired Documents: {', '.join(scheme_data.get('requiredDocsEn', []))}",
            "source_file": "admin_pdf_upload",
            "source_url": scheme_data.get('officialUrl', '')
        }
        docs.append(new_chunk)

        with open(RAG_DOCS_PATH, 'w', encoding='utf-8') as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error updating rag_documents.json: {e}")


@admin_bp.route('/stats', methods=['GET'])
def get_stats():
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    schemes = load_all_schemes()
    user_count = 0
    try:
        user_count = users_collection.count_documents({})
    except Exception:
        pass

    categories = set(s.get('category', 'general') for s in schemes if s.get('category'))

    return jsonify({
        'total_schemes': len(schemes),
        'total_users': user_count,
        'categories_count': len(categories),
        'system_status': 'Operational',
        'rag_status': 'Vectorstore Synchronized'
    }), 200


@admin_bp.route('/schemes', methods=['GET'])
def list_schemes():
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    schemes = load_all_schemes()
    return jsonify(schemes), 200


@admin_bp.route('/schemes/extract-pdf', methods=['POST'])
def extract_pdf():
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    if 'file' not in request.files:
        return jsonify({'message': 'No PDF file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'Empty file selected'}), 400

    try:
        # Extract text using PyPDF
        pdf_stream = io.BytesIO(file.read())
        reader = pypdf.PdfReader(pdf_stream)
        raw_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            raw_text += f"\n--- Page {i+1} ---\n" + text

        raw_text_clean = raw_text.strip()
        if not raw_text_clean:
            return jsonify({'message': 'Could not extract text from this PDF (it might be scanned/image-only).'}), 400

        # Now extract structured information with AI (Groq or fallback)
        groq_api_key = os.getenv("GROQ_API_KEY")
        extracted_data = None

        # Try multiple Groq models in order of preference
        GROQ_MODELS = [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
        ]
        if groq_api_key:
            for model_name in GROQ_MODELS:
                try:
                    from langchain_groq import ChatGroq
                    llm = ChatGroq(
                        model_name=model_name,
                        groq_api_key=groq_api_key,
                        temperature=0.1
                    )

                    prompt = f"""You are an expert Indian Government Scheme data extractor.
Read the PDF text below carefully and extract ALL information into a valid JSON object.

STRICT RULES:
1. Return ONLY the raw JSON — no markdown, no backticks, no extra explanation.
2. NEVER return null for benefitEn, benefitAmount, or whyEligibleEn — these are MANDATORY.
   - For benefitEn: describe the financial assistance, stipend, fee reimbursement, subsidy etc.
   - For benefitAmount: give the amount or say "Fee reimbursement + stipend" or "As per scheme norms"
   - For whyEligibleEn: list who qualifies — caste (SC/ST/OBC), income limit, class/level, state, gender
3. Translate all English fields to Hindi for the *Hi fields.
4. category MUST be one of: farming, education, healthcare, finance, housing, women, employment, general

OUTPUT JSON:
{{
  "titleEn": "<exact scheme name from text>",
  "titleHi": "<scheme name in Hindi>",
  "category": "<category>",
  "categoryLabelEn": "<e.g. Education & Scholarship>",
  "categoryLabelHi": "<e.g. शिक्षा एवं छात्रवृत्ति>",
  "ministryEn": "<implementing ministry or department>",
  "ministryHi": "<ministry name in Hindi>",
  "benefitEn": "<describe ALL benefits: fee reimbursement, stipend amount, allowances, etc. from the text>",
  "benefitHi": "<same in Hindi>",
  "benefitAmount": "<concise: e.g. Fee reimbursement + ₹230/month stipend OR ₹6,000/year>",
  "whyEligibleEn": "<ALL eligibility criteria: target community (SC/ST/OBC), income limit, education level, age, gender, state>",
  "whyEligibleHi": "<same in Hindi>",
  "descriptionEn": "<2-3 sentence overview of the scheme>",
  "descriptionHi": "<same in Hindi>",
  "requiredDocsEn": ["<all documents mentioned: Aadhaar, income certificate, caste certificate, etc.>"],
  "requiredDocsHi": ["<same in Hindi>"],
  "officialUrl": "<Look carefully for any URL/website/portal link in the PDF text (e.g., scholarships.gov.in, pfms.nic.in, pmkisan.gov.in, etc.). Extract the ACTUAL scheme-specific URL. Only use https://myscheme.gov.in if absolutely no URL is found>",
  "helplinePhone": "<helpline number or null>",
  "applicationSteps": [
    "<Step 1: First step to apply>",
    "<Step 2: Second step to apply>",
    "<Step 3: Submission / verification step>"
  ],
  "applicationStepsHi": [
    "<Step 1 in Hindi>",
    "<Step 2 in Hindi>",
    "<Step 3 in Hindi>"
  ],
  "criteria": {{
    "targetOccupation": "<Student/Farmer/Women/Any>",
    "maxIncome": <income ceiling as integer, e.g. 250000, or null>,
    "minAge": <minimum age integer or null>,
    "maxAge": <maximum age integer or null>,
    "gender": "<All/Female/Male>",
    "caste": "<SC/ST/OBC/General/All>"
  }}
}}

PDF TEXT:
{raw_text_clean[:9000]}
"""
                    response = llm.invoke(prompt)
                    resp_text = response.content.strip()
                    # Strip any markdown code fences
                    if "```" in resp_text:
                        parts = resp_text.split("```")
                        for part in parts:
                            part = part.strip()
                            if part.startswith("json"):
                                part = part[4:].strip()
                            if part.startswith("{"):
                                resp_text = part
                                break
                    resp_text = resp_text.strip()
                    extracted_data = json.loads(resp_text)
                    print(f"Groq extraction successful with model: {model_name}")
                    break  # success, stop trying more models
                except Exception as e:
                    print(f"Groq LLM extraction error with {model_name}: {e}")
                    continue  # try next model

        # Smarter fallback heuristic if LLM failed or key unavailable
        if not extracted_data:
            import re as _re
            lines = [l.strip() for l in raw_text_clean.split("\n") if l.strip()]
            text_lower = raw_text_clean.lower()

            # Try to find a meaningful title (skip very short lines or common header words)
            title_line = "Uploaded Government Scheme"
            for l in lines[:20]:
                if len(l) > 15 and not l.lower().startswith(("page", "govt", "government of", "ministry", "भारत", "no.", "f.no")):
                    title_line = l[:120]
                    break

            # Detect category from keywords
            cat_map = [
                ("farming",    ["kisan", "farmer", "agriculture", "pm-kisan", "crop", "krishi"]),
                ("education",  ["scholarship", "student", "school", "college", "education", "vidya", "shiksha"]),
                ("healthcare", ["health", "hospital", "medical", "ayushman", "treatment", "swasthya"]),
                ("housing",    ["housing", "awas", "house", "home", "pradhan mantri awas"]),
                ("women",      ["women", "mahila", "beti", "girl", "maternity"]),
                ("employment", ["employment", "rojgar", "skill", "training", "job", "labour", "mazdoor"]),
                ("finance",    ["loan", "mudra", "insurance", "pension", "bima", "jan dhan"]),
            ]
            detected_cat = "general"
            detected_cat_en = "Government Scheme"
            for cat_id, keywords in cat_map:
                if any(kw in text_lower for kw in keywords):
                    detected_cat = cat_id
                    detected_cat_en = cat_id.capitalize()
                    break

            # Try to extract amount using regex
            amt_match = _re.search(r'(?:rs\.?|₹|inr)\s*[\d,]+(?:/[-\w]+)?', text_lower)
            benefit_amount = amt_match.group(0).upper() if amt_match else "Refer official guidelines"

            # Try to find ministry line
            ministry_line = "Government of India"
            for l in lines[:30]:
                if "ministry" in l.lower() or "department" in l.lower() or "mantralaya" in l.lower():
                    ministry_line = l[:100]
                    break

            # Extract description from meaningful paragraphs
            para_lines = [l for l in lines if len(l) > 60]
            desc_text = " ".join(para_lines[:3])[:400] if para_lines else raw_text_clean[:400]

            extracted_data = {
                "titleEn": title_line,
                "titleHi": title_line,
                "category": detected_cat,
                "categoryLabelEn": detected_cat_en,
                "categoryLabelHi": "सरकारी योजना",
                "ministryEn": ministry_line,
                "ministryHi": ministry_line,
                "benefitEn": desc_text[:200],
                "benefitHi": desc_text[:200],
                "benefitAmount": benefit_amount,
                "whyEligibleEn": "Please review the extracted PDF text and update eligibility criteria manually.",
                "whyEligibleHi": "कृपया निकाले गए PDF टेक्स्ट की समीक्षा करें और पात्रता मानदंड अपडेट करें।",
                "descriptionEn": desc_text,
                "descriptionHi": desc_text,
                "requiredDocsEn": ["Aadhaar Card", "Bank Account Passbook", "Proof of Identity", "Passport Photo"],
                "requiredDocsHi": ["आधार कार्ड", "बैंक खाता पासबुक", "पहचान प्रमाण", "पासपोर्ट फोटो"],
                "officialUrl": "https://myscheme.gov.in",
                "helplinePhone": None,
                "applicationProcess": "Visit nearest Common Service Centre (CSC) or apply online.",
                "criteria": {
                    "targetOccupation": "Any",
                    "maxIncome": None,
                    "minAge": 18,
                    "maxAge": None,
                    "gender": "All",
                    "caste": "All"
                }
            }

        extracted_data["rawExcerpt"] = raw_text_clean[:800]
        return jsonify({
            'success': True,
            'extracted': extracted_data,
            'page_count': len(reader.pages)
        }), 200

    except Exception as e:
        return jsonify({'message': f'Failed to process PDF: {str(e)}'}), 500


@admin_bp.route('/schemes/save', methods=['POST'])
def save_scheme():
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    payload = request.get_json()
    if not payload:
        return jsonify({'message': 'No data payload provided'}), 400

    mode = payload.get('mode', 'new')  # 'new' or 'edit'
    scheme_data = payload.get('scheme')

    if not scheme_data:
        return jsonify({'message': 'Scheme data is required'}), 400

    # Ensure theme styling defaults
    scheme_data['themeColor'] = scheme_data.get('themeColor') or '#1E3A8A'
    scheme_data['themeLight'] = scheme_data.get('themeLight') or '#EFF6FF'
    scheme_data['themeDark'] = scheme_data.get('themeDark') or '#0F172A'
    scheme_data['updatedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if mode == 'new':
        if not scheme_data.get('id'):
            clean_title = "".join(c for c in scheme_data.get('titleEn', 'scheme').lower() if c.isalnum() or c == ' ')
            slug = "_".join(clean_title.split()[:4])
            scheme_data['id'] = f"scheme_{slug}_{uuid.uuid4().hex[:6]}"
        scheme_data['createdAt'] = scheme_data['updatedAt']

        # Save to MongoDB
        schemes_collection.update_one(
            {'id': scheme_data['id']},
            {'$set': scheme_data},
            upsert=True
        )

        # Sync to mock_schemes.json, scheme_full.json, and rag_documents.json
        sync_scheme_to_mock_file(scheme_data, is_new=True)
        sync_scheme_to_full_file(scheme_data, is_new=True)
        append_rag_document(scheme_data)

        message = f"New scheme '{scheme_data.get('titleEn')}' published successfully!"

    else:
        # Edit mode
        scheme_id = scheme_data.get('id')
        if not scheme_id:
            return jsonify({'message': 'scheme_id is required for edit mode'}), 400

        # Save update to MongoDB
        schemes_collection.update_one(
            {'id': scheme_id},
            {'$set': scheme_data},
            upsert=True
        )

        # Record history log
        if POLICY_HISTORY_PATH.exists():
            try:
                with open(POLICY_HISTORY_PATH, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = []
                history.append({
                    "scheme_id": scheme_id,
                    "updated_by": admin.get('email', 'admin@gmail.com'),
                    "timestamp": scheme_data['updatedAt'],
                    "change_summary": f"Admin revised scheme guidelines via PDF upload."
                })
                with open(POLICY_HISTORY_PATH, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
            except Exception as he:
                print(f"Could not update policy history: {he}")

        sync_scheme_to_mock_file(scheme_data, is_new=False)
        sync_scheme_to_full_file(scheme_data, is_new=False)
        append_rag_document(scheme_data)
        message = f"Scheme '{scheme_data.get('titleEn')}' guidelines updated successfully!"

    return jsonify({
        'success': True,
        'message': message,
        'scheme': scheme_data
    }), 200


@admin_bp.route('/schemes/<scheme_id>', methods=['DELETE'])
def delete_scheme(scheme_id):
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    try:
        schemes_collection.delete_one({'id': scheme_id})
        # Remove from mock_schemes.json
        if MOCK_SCHEMES_PATH.exists():
            with open(MOCK_SCHEMES_PATH, 'r', encoding='utf-8') as f:
                schemes = json.load(f)
            schemes = [s for s in schemes if s.get('id') != scheme_id]
            with open(MOCK_SCHEMES_PATH, 'w', encoding='utf-8') as f:
                json.dump(schemes, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True, 'message': 'Scheme deleted successfully'}), 200
    except Exception as e:
        return jsonify({'message': f'Failed to delete: {str(e)}'}), 500


@admin_bp.route('/users', methods=['GET'])
def list_users():
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    try:
        users = list(users_collection.find({}, {'_id': 0, 'password': 0, 'reset_otp': 0, 'otp_expiry': 0}))
        return jsonify({'success': True, 'users': users}), 200
    except Exception as e:
        return jsonify({'message': f'Failed to fetch users: {str(e)}'}), 500


@admin_bp.route('/users/<email>', methods=['DELETE'])
def delete_user(email):
    admin, err = verify_admin(request)
    if err:
        return jsonify({'message': err}), 401

    try:
        user = users_collection.find_one({'email': email})
        if not user:
            return jsonify({'message': 'User not found'}), 404

        user_name = user.get('name', 'User')

        # 1. Send Account Deletion SMTP Email before/during deletion
        from app.utils.email_service import send_account_deleted_email
        send_account_deleted_email(email, user_name)

        # 2. Delete user from MongoDB
        users_collection.delete_one({'email': email})

        return jsonify({'success': True, 'message': f'User {email} deleted successfully and notification email sent'}), 200
    except Exception as e:
        return jsonify({'message': f'Failed to delete user: {str(e)}'}), 500

