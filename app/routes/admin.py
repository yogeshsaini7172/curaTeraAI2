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
    """Load combined schemes from MongoDB and mock_schemes.json."""
    schemes = []
    # 1. From MongoDB
    try:
        db_schemes = list(schemes_collection.find({}, {'_id': 0}))
        schemes.extend(db_schemes)
    except Exception as e:
        print(f"Error fetching from MongoDB schemes: {e}")

    # 2. From mock_schemes.json for defaults
    if MOCK_SCHEMES_PATH.exists():
        try:
            with open(MOCK_SCHEMES_PATH, 'r', encoding='utf-8') as f:
                mock_list = json.load(f)
                existing_ids = {s.get('id') for s in schemes}
                for ms in mock_list:
                    if ms.get('id') not in existing_ids:
                        schemes.append(ms)
        except Exception as e:
            print(f"Error reading mock_schemes.json: {e}")

    return schemes

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

        if groq_api_key:
            try:
                from langchain_groq import ChatGroq
                llm = ChatGroq(
                    model_name="llama-3.3-70b-versatile",
                    groq_api_key=groq_api_key,
                    temperature=0.1
                )

                prompt = f"""
You are an expert Government Scheme Parser. Extract structured information from the following official government circular/guideline PDF text into strict valid JSON format.

RULES:
1. Return ONLY the raw JSON object, without any markdown formatting, no ```json or ``` backticks.
2. Provide both English and Hindi translations for key titles and benefits where possible.
3. Make sure 'category' is one of: ['farming', 'education', 'healthcare', 'finance', 'housing', 'women', 'employment', 'general'].

SCHEMA REQUIREMENTS:
{{
  "titleEn": "Full official name of scheme in English",
  "titleHi": "Full official name of scheme in Hindi",
  "category": "one of categories above",
  "categoryLabelEn": "Human readable category label in English (e.g. Agriculture & Farming)",
  "categoryLabelHi": "Human readable category label in Hindi (e.g. कृषि एवं किसानी)",
  "ministryEn": "Implementing Ministry or Department in English",
  "ministryHi": "Implementing Ministry or Department in Hindi",
  "benefitEn": "Summary of benefits provided (e.g. ₹6,000 per year in 3 installments)",
  "benefitHi": "Summary of benefits in Hindi",
  "benefitAmount": "Brief amount phrase (e.g. ₹6,000/year or 50% Subsidy)",
  "whyEligibleEn": "Eligibility summary in English (who qualifies, age, land, income)",
  "whyEligibleHi": "Eligibility summary in Hindi",
  "descriptionEn": "Comprehensive overview description in English (2-3 sentences)",
  "descriptionHi": "Comprehensive overview description in Hindi",
  "requiredDocsEn": ["List", "of", "required", "documents", "in", "English"],
  "requiredDocsHi": ["List", "of", "required", "documents", "in", "Hindi"],
  "officialUrl": "Official portal URL or https://myscheme.gov.in",
  "helplinePhone": "Helpline number or 1800-XXX-XXXX",
  "criteria": {{
    "targetOccupation": "Farmer, Student, Women, Any, etc.",
    "maxIncome": 250000,
    "minAge": 18,
    "maxAge": 60,
    "gender": "All or Female or Male"
  }}
}}

TEXT TO EXTRACT:
{raw_text_clean[:6000]}
"""
                response = llm.invoke(prompt)
                resp_text = response.content.strip()
                if resp_text.startswith("```"):
                    resp_text = resp_text.split("```")[1]
                    if resp_text.startswith("json"):
                        resp_text = resp_text[4:]
                resp_text = resp_text.strip()
                extracted_data = json.loads(resp_text)
            except Exception as e:
                print(f"Groq LLM extraction error: {e}")

        # Fallback heuristic if LLM failed or key unavailable
        if not extracted_data:
            lines = [line.strip() for line in raw_text_clean.split("\n") if line.strip()]
            first_line = lines[0] if lines else "Uploaded Government Scheme"
            extracted_data = {
                "titleEn": first_line[:80],
                "titleHi": first_line[:80],
                "category": "farming" if "farm" in raw_text_clean.lower() or "kisan" in raw_text_clean.lower() else "general",
                "categoryLabelEn": "Government Scheme",
                "categoryLabelHi": "सरकारी योजना",
                "ministryEn": "Ministry of Agriculture & Farmers Welfare" if "kisan" in raw_text_clean.lower() else "Government of India",
                "ministryHi": "भारत सरकार",
                "benefitEn": "Direct Financial Assistance and Welfare Support under Government guidelines.",
                "benefitHi": "सरकारी दिशानिर्देशों के तहत प्रत्यक्ष वित्तीय सहायता और कल्याण सहायता।",
                "benefitAmount": "Refer official guidelines",
                "whyEligibleEn": "Eligible as per latest government notification criteria.",
                "whyEligibleHi": "नवीनतम सरकारी अधिसूचना मानदंडों के अनुसार पात्र।",
                "descriptionEn": raw_text_clean[:300] + "...",
                "descriptionHi": raw_text_clean[:300] + "...",
                "requiredDocsEn": ["Aadhaar Card", "Bank Account Passbook", "Proof of Identity"],
                "requiredDocsHi": ["आधार कार्ड", "बैंक खाता पासबुक", "पहचान प्रमाण"],
                "officialUrl": "https://myscheme.gov.in",
                "helplinePhone": "1800-180-1551",
                "criteria": {
                    "targetOccupation": "Any",
                    "maxIncome": None,
                    "minAge": 18,
                    "maxAge": None,
                    "gender": "All"
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

        # Sync to mock_schemes.json and rag_documents.json
        sync_scheme_to_mock_file(scheme_data, is_new=True)
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

