from flask import Blueprint, request, jsonify
import json
import os
import re
from rag.retriever import retrieve_documents
from models.user import users_collection
from ml.eligibility.engine import evaluate_all_schemes
from pathlib import Path

schemes_bp = Blueprint('schemes', __name__, url_prefix='/api/schemes')

FULL_SCHEMES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "scheme_full.json"
TRANSLATIONS_HI_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "scheme_translations_hi.json"

_TRANSLATIONS_HI = None
_TRANSLATIONS_MTIME = 0

def get_translations_hi():
    global _TRANSLATIONS_HI, _TRANSLATIONS_MTIME
    if TRANSLATIONS_HI_PATH.exists():
        try:
            mtime = os.path.getmtime(TRANSLATIONS_HI_PATH)
            if _TRANSLATIONS_HI is None or mtime > _TRANSLATIONS_MTIME:
                with open(TRANSLATIONS_HI_PATH, 'r', encoding='utf-8') as f:
                    _TRANSLATIONS_HI = json.load(f)
                    _TRANSLATIONS_MTIME = mtime
        except Exception as e:
            if _TRANSLATIONS_HI is None:
                _TRANSLATIONS_HI = {}
    return _TRANSLATIONS_HI or {}

def get_full_schemes():
    if FULL_SCHEMES_PATH.exists():
        with open(FULL_SCHEMES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def determine_category(name: str, text: str):
    combined = (name + " " + text).lower()
    if any(k in combined for k in ['farmer', 'kisan', 'agri', 'crop', 'krishi', 'soil', 'seed', 'dairy']):
        return 'farming', 'Farmer Welfare', 'किसान कल्याण'
    elif any(k in combined for k in ['school', 'scholarship', 'student', 'education', 'shiksha', 'vidya', 'study', 'fellowship']):
        return 'education', 'Education & Girls', 'शिक्षा व छात्रवृत्ति'
    elif any(k in combined for k in ['house', 'housing', 'awas', 'shelter', 'home', 'pucca']):
        return 'housing', 'Housing Support', 'पक्का आवास'
    elif any(k in combined for k in ['health', 'swasthya', 'ayush', 'medical', 'hospital', 'medicine', 'bima', 'treatment']):
        return 'health', 'Health & Medical', 'स्वास्थ्य व इलाज'
    elif any(k in combined for k in ['pension', 'senior', 'vridha', 'widow', 'suraksha', 'security']):
        return 'pension', 'Pension & Security', 'पेंशन व सुरक्षा'
    else:
        return 'business', 'Business & Loans', 'रोजगार व लोन'

def format_retrieved_scheme(doc):
    """
    Format a scheme from scheme_full.json into the frontend Scheme interface.
    """
    benefit_en = "Financial & Technical Assistance under Government Guidelines."
    why_eligible_en = "Open to eligible citizens meeting prescribed scheme norms."
    required_docs = ["Aadhaar Card", "Bank Passbook", "Passport Size Photos"]
    description_en = ""
    application_process = []
    
    sections = doc.get("sections")
    if isinstance(sections, dict):
        benefits_list = sections.get("benefits", [])
        if benefits_list and isinstance(benefits_list, list):
            benefit_en = " ".join(str(b) for b in benefits_list[:2])[:140] + "..."
        elif isinstance(benefits_list, str):
            benefit_en = benefits_list[:140] + "..."

        elig_list = sections.get("eligibility", [])
        if elig_list and isinstance(elig_list, list):
            why_eligible_en = " ".join(str(e) for e in elig_list[:2])[:100] + "..."
        elif isinstance(elig_list, str):
            why_eligible_en = elig_list[:100] + "..."

        docs_list = sections.get("documents_required", [])
        if docs_list and isinstance(docs_list, list) and len(docs_list) > 0:
            clean_docs = [str(d).replace('*', '').strip() for d in docs_list if str(d).strip() and not str(d).startswith('***')]
            if clean_docs:
                required_docs = clean_docs[:4]

        details_list = sections.get("details", [])
        if details_list and isinstance(details_list, list):
            description_en = " ".join(str(d) for d in details_list[:2])[:220] + "..."

        app_list = sections.get("application_process", [])
        if app_list and isinstance(app_list, list):
            for step in app_list:
                s = str(step).strip()
                if re.match(r'^\[?svg\]?(\(.*\))?$', s, re.I) or s.lower() == 'svg':
                    continue
                s = s.replace('***', '').replace('**', '').replace('\\*', '').replace('\ufeff', '').strip()
                if s.startswith('- '):
                    s = s[2:].strip()
                s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
                if s and s.lower() != 'svg':
                    application_process.append(s)
        elif isinstance(app_list, str) and app_list.strip():
            application_process = [app_list.strip()]
    elif isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                title = section.get("title", "").lower()
                content = section.get("content", "")
                if "benefit" in title:
                    benefit_en = content[:140] + "..."
                elif "eligibility" in title:
                    why_eligible_en = content[:100] + "..."
                elif "detail" in title and not description_en:
                    description_en = content[:220] + "..."
                elif "application" in title or "apply" in title or "process" in title:
                    application_process.append(content)

    scheme_name = doc.get("scheme_name", "Government Scheme")
    scheme_id = doc.get("scheme_id", "S000")
    if not description_en:
        description_en = doc.get("raw_text", scheme_name)[:220] + "..."

    cat_id, cat_en, cat_hi = determine_category(scheme_name, description_en)

    hi_trans = get_translations_hi().get(scheme_id)
    if not hi_trans:
        try:
            from app.utils.translator import ensure_scheme_translated_async
            ensure_scheme_translated_async(doc)
        except Exception:
            pass
        hi_trans = {}

    title_hi = hi_trans.get("titleHi") or scheme_name
    benefit_hi = hi_trans.get("benefitHi") or benefit_en
    why_eligible_hi = hi_trans.get("whyEligibleHi") or why_eligible_en
    description_hi = hi_trans.get("descriptionHi") or description_en
    required_docs_hi = hi_trans.get("requiredDocsHi") or required_docs
    application_process_hi = hi_trans.get("applicationProcessHi") or application_process

    return {
        "id": scheme_id,
        "titleEn": scheme_name,
        "titleHi": title_hi,
        "category": cat_id,
        "categoryLabelEn": cat_en,
        "categoryLabelHi": cat_hi,
        "ministryEn": doc.get("implementing_authority", "Government of India"),
        "ministryHi": doc.get("implementing_authority", "भारत सरकार"),
        "benefitEn": benefit_en,
        "benefitHi": benefit_hi,
        "benefitAmount": "Govt Benefit",
        "benefitAmountEn": "Govt Benefit",
        "benefitAmountHi": "सरकारी सहायता",
        "isEligible": False,
        "matchPercentage": 0,
        "whyEligibleEn": why_eligible_en,
        "whyEligibleHi": why_eligible_hi,
        "descriptionEn": description_en,
        "descriptionHi": description_hi,
        "requiredDocsEn": required_docs,
        "requiredDocsHi": required_docs_hi,
        "applicationProcess": application_process,
        "applicationProcessEn": application_process,
        "applicationProcessHi": application_process_hi,
        "officialUrl": "https://www.myscheme.gov.in",
        "helplinePhone": "1800115555",
        "themeColor": "#0F172A",
        "themeLight": "#F8FAFC",
        "themeDark": "#0F172A"
    }

def get_all_schemes_combined():
    full_docs = get_full_schemes()
    return [format_retrieved_scheme(d) for d in full_docs]

def extract_user_email():
    email = request.args.get('email')
    if email:
        return email
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split(" ")
        token = parts[1] if len(parts) == 2 and parts[0] == "Bearer" else auth_header
        try:
            import jwt
            from app.routes.auth import SECRET_KEY
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return data.get('email')
        except Exception:
            pass
    return None

RULES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "eligibility_rules.csv"
_RULES_DF = None

def get_rules_df():
    global _RULES_DF
    if _RULES_DF is None and RULES_PATH.exists():
        try:
            from ml.eligibility.rule_parser import load_rules
            _RULES_DF = load_rules(str(RULES_PATH))
        except Exception as e:
            print(f"Error loading eligibility rules: {e}")
    return _RULES_DF

def is_profile_proper(profile):
    """
    Real-world eligibility validation:
    A user profile is ONLY considered proper and eligible for evaluation
    if the citizen has actually provided their demographic and socio-economic details.
    Blank/incomplete profiles MUST NOT receive any scheme eligibility.
    """
    if not profile or not isinstance(profile, dict):
        return False
        
    for k in ('age', 'occupation', 'annualIncome', 'income', 'state', 'social_category', 'category', 'eligibleSchemeIds', 'eligible_schemes'):
        val = profile.get(k)
        if val is not None and str(val).strip() not in ('', 'None', 'null', '[]', '{}'):
            return True
    return False

def evaluate_schemes_for_profile(schemes_list, profile):
    """
    Evaluates each scheme strictly against the citizen's actual profile details.
    Eligibility is determined SOLELY by:
    1. Explicit eligible scheme IDs stored in the user profile (set by the Agent), AND/OR
    2. The ML deterministic eligibility engine evaluating rules against profile attributes.
    Strictly NO heuristic or hardcoded category guesses.
    """
    if not is_profile_proper(profile):
        for s in schemes_list:
            s['isEligible'] = False
            s['matchPercentage'] = 0
        return schemes_list

    eligible_ids = set()

    # 1. Check explicit eligible scheme IDs in profile (from agent / chat / updates)
    for raw_id in (profile.get('eligibleSchemeIds') or profile.get('eligible_schemes') or []):
        if isinstance(raw_id, dict):
            raw_id = raw_id.get('scheme_id') or raw_id.get('id')
        if raw_id:
            s_val = str(raw_id).strip()
            eligible_ids.add(s_val)
            eligible_ids.add(s_val.upper())
            eligible_ids.add(s_val.lower())

    # 2. Run deterministic eligibility rules engine against the citizen's profile
    rules_df = get_rules_df()
    if rules_df is not None:
        try:
            eval_profile = dict(profile)
            if 'annualIncome' in profile and 'income' not in eval_profile:
                eval_profile['income'] = profile['annualIncome']
            if 'category' in profile and 'social_category' not in eval_profile:
                eval_profile['social_category'] = profile['category']
            if 'isStudent' in profile and 'education' not in eval_profile:
                eval_profile['education'] = 'student' if profile['isStudent'] else 'other'

            results = evaluate_all_schemes(eval_profile, rules_df)
            for res in results:
                if res.get('status') == 'eligible':
                    sid = str(res.get('scheme_id', '')).strip()
                    if sid:
                        eligible_ids.add(sid)
                        eligible_ids.add(sid.upper())
                        eligible_ids.add(sid.lower())
        except Exception as err:
            print(f"Eligibility engine evaluation error: {err}")

    # 3. Mark each scheme strictly according to verified eligibility
    for s in schemes_list:
        s_id = str(s.get('id', '')).strip()
        is_eligible = (
            s_id in eligible_ids or 
            s_id.upper() in eligible_ids or 
            s_id.lower() in eligible_ids
        )
        s['isEligible'] = is_eligible
        s['matchPercentage'] = 100 if is_eligible else 0
        
    return schemes_list

@schemes_bp.route('', methods=['GET'])
@schemes_bp.route('/', methods=['GET'])
def get_schemes():
    email = extract_user_email()
    
    # Query parameters
    page_param = request.args.get('page')
    limit_param = request.args.get('limit')
    category = request.args.get('category', 'all').lower().strip()
    query = request.args.get('q', '').lower().strip()
    all_raw = request.args.get('all') == 'true'
    
    schemes = get_all_schemes_combined()
    
    if not schemes:
        return jsonify({
            "schemes": [],
            "total": 0,
            "page": 1,
            "limit": 10,
            "totalPages": 0,
            "hasMore": False,
            "eligibleCount": 0
        }), 200

    # 1. Reset all schemes to not eligible
    for s in schemes:
        s['isEligible'] = False
        s['matchPercentage'] = 0
        
    # 2. Extract profile from MongoDB and LangGraph checkpointer
    profile = None
    if email:
        db_profile = {}
        user = users_collection.find_one({'email': email})
        if user and user.get('profile'):
            db_profile = user.get('profile') or {}
        
        citizen_profile = {}
        try:
            from agents.graph import build_graph
            graph = build_graph()
            state = graph.get_state({"configurable": {"thread_id": email}})
            if state and state.values:
                citizen_profile = state.values.get("citizen_profile") or {}
        except Exception:
            pass

        if db_profile or citizen_profile:
            profile = {**citizen_profile, **db_profile}

    # 3. Strictly evaluate schemes against user profile
    schemes = evaluate_schemes_for_profile(schemes, profile)
                    
    # Always sort eligible schemes first, highest match first
    schemes = sorted(schemes, key=lambda x: (not x.get('isEligible', False), -x.get('matchPercentage', 0)))

    # 2. Filter by Category
    if category == 'eligible':
        filtered = [s for s in schemes if s.get('isEligible')]
    elif category and category != 'all':
        filtered = [s for s in schemes if s.get('category', '').lower() == category]
    else:
        filtered = schemes

    # 3. Filter by Search Query
    if query:
        filtered = [
            s for s in filtered
            if query in s.get('titleEn', '').lower()
            or query in s.get('titleHi', '').lower()
            or query in s.get('benefitEn', '').lower()
            or query in s.get('benefitHi', '').lower()
            or query in s.get('categoryLabelEn', '').lower()
            or query in s.get('categoryLabelHi', '').lower()
            or query in s.get('ministryEn', '').lower()
            or query in s.get('descriptionEn', '').lower()
            or query in s.get('descriptionHi', '').lower()
        ]

    total = len(filtered)
    eligible_count = sum(1 for s in schemes if s.get('isEligible'))

    # If caller specifically asked for raw unpaginated array
    if all_raw:
        return jsonify(filtered), 200

    # 4. Pagination
    try:
        page = max(1, int(page_param)) if page_param else 1
    except ValueError:
        page = 1

    try:
        limit = max(1, min(50, int(limit_param))) if limit_param else 10
    except ValueError:
        limit = 10

    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 0
    start = (page - 1) * limit
    end = start + limit
    page_items = filtered[start:end]
    has_more = end < total

    return jsonify({
        "schemes": page_items,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": total_pages,
        "hasMore": has_more,
        "eligibleCount": eligible_count
    }), 200

@schemes_bp.route('/search', methods=['GET'])
def search_schemes():
    query = request.args.get('q', '')
    email = request.args.get('email')
    
    if not query:
        return jsonify([])
        
    all_schemes = get_all_schemes_combined()
    results = []
    seen = set()
    
    # 1. RAG semantic search if available
    try:
        docs = retrieve_documents(query, k=10)
        scheme_map = {s["id"]: s for s in all_schemes}
        for d in docs:
            scheme_id = d.metadata.get('scheme_id')
            if scheme_id and scheme_id in scheme_map and scheme_id not in seen:
                seen.add(scheme_id)
                results.append(scheme_map[scheme_id])
    except Exception as e:
        pass

    # 2. Text-based keyword match fallback across full database
    q_lower = query.lower().strip()
    for s in all_schemes:
        if s.get('id') not in seen:
            t_en = s.get('titleEn', '').lower()
            t_hi = s.get('titleHi', '').lower()
            b_en = s.get('benefitEn', '').lower()
            b_hi = s.get('benefitHi', '').lower()
            c_en = s.get('categoryLabelEn', '').lower()
            c_hi = s.get('categoryLabelHi', '').lower()
            if q_lower in t_en or q_lower in t_hi or q_lower in b_en or q_lower in b_hi or q_lower in c_en or q_lower in c_hi:
                seen.add(s.get('id'))
                results.append(s)

    # 3. Evaluate eligibility if profile is proper
    for s in results:
        s['isEligible'] = False
        s['matchPercentage'] = 0

    profile = None
    if email:
        user = users_collection.find_one({'email': email})
        if user and user.get('profile'):
            profile = user.get('profile')
        else:
            try:
                from agents.graph import build_graph
                graph = build_graph()
                state = graph.get_state({"configurable": {"thread_id": email}})
                if state and state.values:
                    profile = state.values.get("citizen_profile")
            except Exception:
                pass

    results = evaluate_schemes_for_profile(results, profile)
    results = sorted(results, key=lambda x: (not x.get('isEligible', False), -x.get('matchPercentage', 0)))

    return jsonify(results), 200

@schemes_bp.route('', methods=['POST'])
@schemes_bp.route('/', methods=['POST'])
@schemes_bp.route('/add', methods=['POST'])
def add_scheme():
    """
    Admin endpoint to add a new scheme.
    - Saves the scheme to scheme_full.json.
    - Automatically triggers AI translation to Hindi and saves to scheme_translations_hi.json.
    - Returns the full dual-language scheme.
    """
    data = request.get_json() or {}
    scheme_name = data.get("scheme_name") or data.get("title") or data.get("titleEn")
    if not scheme_name:
        return jsonify({"error": "scheme_name is required"}), 400

    full_docs = get_full_schemes()
    
    # Auto-generate next scheme_id (e.g. S051) if not provided
    scheme_id = data.get("scheme_id") or data.get("id")
    if not scheme_id:
        existing_ids = []
        for d in full_docs:
            sid = str(d.get("scheme_id", ""))
            if sid.startswith("S") and sid[1:].isdigit():
                existing_ids.append(int(sid[1:]))
        next_num = (max(existing_ids) + 1) if existing_ids else (len(full_docs) + 1)
        scheme_id = f"S{next_num:03d}"

    # Build standard scheme document structure
    sections = data.get("sections")
    if not sections or not isinstance(sections, dict):
        sections = {
            "details": [data.get("description") or data.get("descriptionEn", "")],
            "benefits": [data.get("benefit") or data.get("benefitEn", "")],
            "eligibility": [data.get("eligibility") or data.get("whyEligibleEn", "")],
            "documents_required": data.get("documents_required") or data.get("requiredDocsEn", []),
            "application_process": data.get("application_process") or data.get("applicationProcessEn", [])
        }

    new_doc = {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "jurisdiction_type": data.get("jurisdiction_type", "Central"),
        "jurisdiction": data.get("jurisdiction", "India"),
        "implementing_authority": data.get("implementing_authority") or data.get("ministry") or data.get("ministryEn") or "Government of India",
        "sections": sections
    }

    # 1. Save to scheme_full.json
    full_docs.append(new_doc)
    try:
        with open(FULL_SCHEMES_PATH, "w", encoding="utf-8") as f:
            json.dump(full_docs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({"error": f"Failed to save scheme: {str(e)}"}), 500

    # 2. Auto-translate immediately to Hindi and save to scheme_translations_hi.json
    from app.utils.translator import translate_single_scheme
    hi_trans = translate_single_scheme(new_doc)

    # 3. Format and return full scheme
    formatted = format_retrieved_scheme(new_doc)
    return jsonify({
        "success": True,
        "message": f"Scheme {scheme_id} added and translated to Hindi successfully!",
        "scheme": formatted
    }), 201

