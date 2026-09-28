import os
import json
import cloudinary
import cloudinary.uploader
from pathlib import Path
from dotenv import load_dotenv

# Load env
load_dotenv('.env')

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

FRONTEND_ASSETS_DIR = Path("../CuraTeraApp/assets")
FULL_SCHEMES_PATH = Path("data/processed/scheme_full.json")

# Category to local asset mapping
CATEGORY_FILES = {
    "farming": "scheme_kisan.jpg",
    "housing": "scheme_awas.jpg",
    "health": "scheme_health.jpg",
    "education": "scheme_education.jpg",
    "pension": "scheme_insurance.jpg",
    "business": "scheme_business.jpg"
}

# Add default fallback
DEFAULT_IMAGE = "scheme_solar.jpg"

def determine_category(name: str, text: str):
    combined = (name + " " + text).lower()
    if any(k in combined for k in ['farmer', 'kisan', 'agri', 'crop', 'krishi', 'soil', 'seed', 'dairy']):
        return 'farming'
    elif any(k in combined for k in ['school', 'scholarship', 'student', 'education', 'shiksha', 'vidya', 'study', 'fellowship']):
        return 'education'
    elif any(k in combined for k in ['house', 'housing', 'awas', 'shelter', 'home', 'pucca']):
        return 'housing'
    elif any(k in combined for k in ['health', 'swasthya', 'ayush', 'medical', 'hospital', 'medicine', 'bima', 'treatment']):
        return 'health'
    elif any(k in combined for k in ['pension', 'senior', 'vridha', 'widow', 'suraksha', 'security']):
        return 'pension'
    else:
        return 'business'

def main():
    print("Uploading images to Cloudinary with compression...")
    uploaded_urls = {}
    
    # Upload categories
    for cat, filename in CATEGORY_FILES.items():
        filepath = FRONTEND_ASSETS_DIR / filename
        if filepath.exists():
            print(f"Uploading {cat} ({filename})...")
            res = cloudinary.uploader.upload(
                str(filepath), 
                folder="curatera_schemes",
                # Cloudinary automatic format and quality compression
                transformation=[
                    {'quality': "auto", 'fetch_format': "auto"}
                ]
            )
            # Use the secure URL
            uploaded_urls[cat] = res.get('secure_url')
            print(f"Success: {uploaded_urls[cat]}")
        else:
            print(f"File not found: {filepath}")

    # Upload default fallback
    default_path = FRONTEND_ASSETS_DIR / DEFAULT_IMAGE
    default_url = ""
    if default_path.exists():
        print(f"Uploading default ({DEFAULT_IMAGE})...")
        res = cloudinary.uploader.upload(
            str(default_path), 
            folder="curatera_schemes",
            transformation=[{'quality': "auto", 'fetch_format': "auto"}]
        )
        default_url = res.get('secure_url')
        print(f"Success Default: {default_url}")

    if not FULL_SCHEMES_PATH.exists():
        print("scheme_full.json not found!")
        return

    print("\nUpdating scheme_full.json...")
    with open(FULL_SCHEMES_PATH, 'r', encoding='utf-8') as f:
        schemes = json.load(f)

    updated_count = 0
    for scheme in schemes:
        name = scheme.get('scheme_name', '')
        desc = ""
        sections = scheme.get('sections', {})
        if isinstance(sections, dict):
            details = sections.get('details', [])
            if details:
                desc = str(details[0])
        elif isinstance(sections, list):
            for sec in sections:
                if isinstance(sec, dict) and 'detail' in str(sec.get('title','')).lower():
                    desc = str(sec.get('content',''))
        
        cat = determine_category(name, desc)
        
        # Assign URL based on category
        img_url = uploaded_urls.get(cat, default_url)
        if img_url:
            scheme['image_url'] = img_url
            updated_count += 1

    with open(FULL_SCHEMES_PATH, 'w', encoding='utf-8') as f:
        json.dump(schemes, f, ensure_ascii=False, indent=2)

    print(f"Updated {updated_count} schemes with Cloudinary URLs!")

if __name__ == '__main__':
    main()
