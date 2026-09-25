from flask import Blueprint, request, jsonify
import json
import os
from rag.retriever import retrieve_documents
from models.user import users_collection
from ml.eligibility.engine import evaluate_all_schemes
from pathlib import Path

schemes_bp = Blueprint('schemes', __name__, url_prefix='/api/schemes')

MOCK_SCHEMES_PATH = Path(__file__).parent / "mock_schemes.json"
FULL_SCHEMES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "scheme_full.json"

def get_mock_schemes():
    if MOCK_SCHEMES_PATH.exists():
        with open(MOCK_SCHEMES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_full_schemes():
    if FULL_SCHEMES_PATH.exists():
        with open(FULL_SCHEMES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def format_retrieved_scheme(doc):
    """
    Format a scheme from scheme_full.json into the frontend Scheme interface.
    """
    # Extract benefit from sections if available
    benefit_en = "Financial Assistance"
    why_eligible_en = "Check official guidelines"
    
    if "sections" in doc:
        for section in doc["sections"]:
            title = section.get("title", "").lower()
            if "benefit" in title:
                benefit_en = section.get("content", benefit_en)[:150] + "..."
            elif "eligibility" in title:
                why_eligible_en = section.get("content", why_eligible_en)[:100] + "..."
                
    return {
        "id": doc.get("scheme_id", "unknown"),
        "titleEn": doc.get("scheme_name", "Unknown Scheme"),
        "titleHi": doc.get("scheme_name", "Unknown Scheme"), # Fallback
        "category": "farming", # Default
        "categoryLabelEn": "Government Scheme",
        "categoryLabelHi": "सरकारी योजना",
        "ministryEn": doc.get("implementing_authority", "Govt of India"),
        "ministryHi": doc.get("implementing_authority", "भारत सरकार"),
        "benefitEn": benefit_en,
        "benefitHi": benefit_en,
        "benefitAmount": "Refer to docs",
        "isEligible": False,
        "matchPercentage": 50,
        "whyEligibleEn": why_eligible_en,
        "whyEligibleHi": why_eligible_en,
        "descriptionEn": doc.get("raw_text", "")[:200] + "...",
        "descriptionHi": doc.get("raw_text", "")[:200] + "...",
        "requiredDocsEn": ["Aadhaar Card", "Bank Passbook"],
        "requiredDocsHi": ["आधार कार्ड", "बैंक पासबुक"],
        "officialUrl": "https://myscheme.gov.in",
        "helplinePhone": "1076",
        "themeColor": "#0F172A",
        "themeLight": "#F8FAFC",
        "themeDark": "#0F172A"
    }

@schemes_bp.route('/', methods=['GET'])
def get_schemes():
    email = request.args.get('email')
    schemes = get_mock_schemes()
    
    if not schemes:
        return jsonify({"message": "No schemes available", "schemes": []}), 200
        
    if email:
        user = users_collection.find_one({'email': email})
        if user and user.get('profile'):
            profile = user.get('profile')
            
            # Simple fallback check since evaluate_all_schemes expects different inputs
            # In a full integration, you would use evaluate_all_schemes here.
            # For demonstration, we simulate top eligible sorting:
            for s in schemes:
                # Mock matching logic
                if profile.get('occupation') == 'Student' and 'education' in s.get('category', ''):
                    s['isEligible'] = True
                    s['matchPercentage'] = 100
                elif profile.get('occupation') == 'Farmer' and 'farming' in s.get('category', ''):
                    s['isEligible'] = True
                    s['matchPercentage'] = 100
                else:
                    s['isEligible'] = False
                    s['matchPercentage'] = 50
                    
            # Sort eligible first
            schemes = sorted(schemes, key=lambda x: (not x.get('isEligible', False), -x.get('matchPercentage', 0)))

    return jsonify(schemes), 200

@schemes_bp.route('/search', methods=['GET'])
def search_schemes():
    query = request.args.get('q', '')
    email = request.args.get('email')
    
    if not query:
        return jsonify([])
        
    # Use FAISS semantic search (completely free, no LLM tokens)
    docs = retrieve_documents(query, k=5)
    
    # docs is a list of Document objects from Langchain
    full_schemes = get_full_schemes()
    scheme_map = {s["scheme_id"]: s for s in full_schemes}
    
    results = []
    seen = set()
    
    for d in docs:
        scheme_id = d.metadata.get('scheme_id')
        if scheme_id and scheme_id not in seen:
            seen.add(scheme_id)
            if scheme_id in scheme_map:
                formatted = format_retrieved_scheme(scheme_map[scheme_id])
                results.append(formatted)
                
    # If FAISS returns empty or we want to fallback to mock schemes for demo purposes:
    if not results:
        mock_schemes = get_mock_schemes()
        q_lower = query.lower()
        for s in mock_schemes:
            if q_lower in s.get('titleEn', '').lower() or q_lower in s.get('titleHi', '').lower():
                results.append(s)

    # Sort if email is provided
    if email:
        user = users_collection.find_one({'email': email})
        if user and user.get('profile'):
            profile = user.get('profile')
            for s in results:
                if profile.get('occupation') == 'Student' and 'education' in s.get('category', ''):
                    s['isEligible'] = True
                    s['matchPercentage'] = 100
            results = sorted(results, key=lambda x: (not x.get('isEligible', False), -x.get('matchPercentage', 0)))

    return jsonify(results), 200
