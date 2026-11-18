import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('curaTeraAI2/.env')

uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(uri)
db = client[os.getenv('MONGODB_DB_NAME', 'schemeDatabase')]
schemes_col = db['schemes']

mock_schemes_path = 'curaTeraAI2/app/routes/mock_schemes.json'

schemes = [
  {
    'id': 'SCHEME-PMKISAN-01',
    'titleEn': 'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)',
    'titleHi': 'प्रधानमंत्री किसान सम्मान निधि योजना',
    'ministryEn': 'Ministry of Agriculture and Farmers Welfare',
    'ministryHi': 'कृषि एवं किसान कल्याण मंत्रालय',
    'category': 'farming',
    'benefitEn': '₹6,000 per year directly into bank accounts in 3 equal four-monthly installments.',
    'benefitHi': 'प्रति वर्ष ₹6,000 तीन समान किस्तों में सीधे बैंक खाते में।',
    'benefitAmount': '₹6,000 / Year',
    'descriptionEn': 'Income support scheme for small and marginal farmers to provide financial assistance for agricultural inputs and domestic needs.',
    'descriptionHi': 'भारत सरकार द्वारा सभी पात्र किसान परिवारों को कृषि आवश्यकताओं की पूर्ति हेतु आय सहायता।',
    'criteriaEn': 'Small and marginal farmer families with cultivable landholding up to 2 hectares.',
    'criteriaHi': '2 हेक्टेयर तक की कृषि योग्य भूमि वाले सभी भूमिधारक किसान परिवार।',
    'requiredDocsEn': ['Aadhaar Card', 'Land Ownership Record (Khatauni)', 'Bank Passbook Details', 'Mobile linked to Aadhaar'],
    'status': 'active',
    'officialUrl': 'https://pmkisan.gov.in'
  },
  {
    'id': 'SCHEME-PMJAY-02',
    'titleEn': 'Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana (PM-JAY)',
    'titleHi': 'आयुष्मान भारत - प्रधानमंत्री जन आरोग्य योजना',
    'ministryEn': 'Ministry of Health and Family Welfare',
    'ministryHi': 'स्वास्थ्य एवं परिवार कल्याण मंत्रालय',
    'category': 'healthcare',
    'benefitEn': 'Cashless health insurance coverage up to ₹5 Lakh per family per year for secondary and tertiary hospital care.',
    'benefitHi': 'प्रति परिवार प्रति वर्ष ₹5 लाख तक का कैशलेस स्वास्थ्य बीमा उपचार।',
    'benefitAmount': '₹5,00,000 / Year',
    'descriptionEn': 'World\'s largest government-funded healthcare scheme targeting poor and vulnerable families based on SECC 2011 criteria.',
    'descriptionHi': 'गरीब और कमजोर परिवारों के लिए माध्यमिक और तृतीयक देखभाल हेतु कैशलेस स्वास्थ्य कवर।',
    'criteriaEn': 'Families identified based on deprivation and occupational criteria of SECC 2011.',
    'criteriaHi': 'SECC 2011 सूची में शामिल ग्रामीण व शहरी गरीब परिवार।',
    'requiredDocsEn': ['Aadhaar Card', 'Ration Card', 'Ayushman Golden Card', 'Income Certificate'],
    'status': 'active',
    'officialUrl': 'https://pmjay.gov.in'
  },
  {
    'id': 'SCHEME-PMAY-03',
    'titleEn': 'Pradhan Mantri Awas Yojana - Gramin (PMAY-G)',
    'titleHi': 'प्रधानमंत्री आवास योजना - ग्रामीण',
    'ministryEn': 'Ministry of Rural Development',
    'ministryHi': 'ग्रामीण विकास मंत्रालय',
    'category': 'housing',
    'benefitEn': 'Financial assistance of ₹1.20 Lakh in plains and ₹1.30 Lakh in hilly states for pucca house construction.',
    'benefitHi': 'मैदानी क्षेत्रों में ₹1.20 लाख और पहाड़ी क्षेत्रों में ₹1.30 लाख की पक्के मकान निर्माण सहायता।',
    'benefitAmount': '₹1,20,000',
    'descriptionEn': 'Provides pucca houses with basic amenities to all houseless households and those living in kutcha houses.',
    'descriptionHi': 'सभी बेघर परिवारों और कच्चे मकानों में रहने वालों को बुनियादी सुविधाओं युक्त पक्का आवास।',
    'criteriaEn': 'Homeless or living in zero, one or two room kutcha houses according to SECC 2011 data.',
    'criteriaHi': 'बेघर परिवार या कच्चे व जीर्ण-शीर्ण मकानों में रहने वाले परिवार।',
    'requiredDocsEn': ['Aadhaar Card', 'Bank Account Passbook', 'MGNREGA Job Card Number', 'Land Registry Proof'],
    'status': 'active',
    'officialUrl': 'https://pmayg.nic.in'
  },
  {
    'id': 'SCHEME-MUDRA-04',
    'titleEn': 'Pradhan Mantri MUDRA Yojana (PMMY)',
    'titleHi': 'प्रधानमंत्री मुद्रा योजना',
    'ministryEn': 'Ministry of Finance',
    'ministryHi': 'वित्त मंत्रालय',
    'category': 'finance',
    'benefitEn': 'Collateral-free business loans up to ₹10 Lakh in Shishu (up to ₹50k), Kishore (up to ₹5L), and Tarun (up to ₹10L).',
    'benefitHi': 'शिशु, किशोर और तरुण श्रेणियों में बिना गारंटी ₹10 लाख तक का व्यवसाय ऋण।',
    'benefitAmount': 'Up to ₹10,00,000',
    'descriptionEn': 'Provides collateral-free loans to micro and small non-corporate non-farm enterprises for income generating activities.',
    'descriptionHi': 'सूक्ष्म एवं लघु उद्यमियों को अपने व्यवसाय शुरू करने या विस्तार के लिए वित्तीय सहायता।',
    'criteriaEn': 'Any Indian citizen having a viable business plan for non-farm income generation.',
    'criteriaHi': 'गैर-कृषि क्षेत्र में आय-सृजक गतिविधि शुरू करने वाले कोई भी भारतीय नागरिक।',
    'requiredDocsEn': ['Aadhaar Card', 'PAN Card', 'Business Proof / Udyam Certificate', 'Last 6 Months Bank Statement'],
    'status': 'active',
    'officialUrl': 'https://www.mudra.org.in'
  },
  {
    'id': 'SCHEME-PMKVY-05',
    'titleEn': 'Pradhan Mantri Kaushal Vikas Yojana (PMKVY 4.0)',
    'titleHi': 'प्रधानमंत्री कौशल विकास योजना',
    'ministryEn': 'Ministry of Skill Development and Entrepreneurship',
    'ministryHi': 'कौशल विकास एवं उद्यमशीलता मंत्रालय',
    'category': 'employment',
    'benefitEn': 'Free industry-aligned short term skill training, soft skills, placement support, and ₹8,000 monetary incentive.',
    'benefitHi': 'निःशुल्क उद्योग-उन्मुख कौशल प्रशिक्षण, प्रमाणन और ₹8,000 का मौद्रिक प्रोत्साहन।',
    'benefitAmount': 'Free Training + ₹8,000',
    'descriptionEn': 'Skill certification initiative to encourage youth to take up industry-relevant skill training for better livelihoods.',
    'descriptionHi': 'उद्योग की आवश्यकताओं के अनुसार युवाओं को तकनीकी और व्यावहारिक कौशल प्रशिक्षण।',
    'criteriaEn': 'Indian youth aged 15-45 who are school/college dropouts or looking for livelihood skills.',
    'criteriaHi': '15 से 45 वर्ष आयु वर्ग के भारतीय युवा जो रोजगार के लिए कौशल प्रशिक्षण चाहते हैं।',
    'requiredDocsEn': ['Aadhaar Card', 'Educational Certificate / Marksheet', 'Bank Account Passbook', 'Passport Size Photograph'],
    'status': 'active',
    'officialUrl': 'https://www.pmkvyofficial.org'
  },
  {
    'id': 'SCHEME-BETI-06',
    'titleEn': 'Beti Bachao Beti Padhao (BBBP)',
    'titleHi': 'बेटी बचाओ बेटी पढ़ाओ योजना',
    'ministryEn': 'Ministry of Women and Child Development',
    'ministryHi': 'महिला एवं बाल विकास मंत्रालय',
    'category': 'women',
    'benefitEn': 'Integrated benefits including girl child welfare awareness, zero-balance Sukanya account linkage, and 8.2% annual interest.',
    'benefitHi': 'बालिकाओं की सुरक्षा, शिक्षा और सुकन्या समृद्धि खाते में 8.2% उच्च ब्याज दर बचत।',
    'benefitAmount': 'Education & Welfare Subsidies',
    'descriptionEn': 'National initiative to address declining Child Sex Ratio (CSR) and promote girl child survival, protection, and education.',
    'descriptionHi': 'बालिकाओं के सशक्तिकरण, उच्च शिक्षा और सामाजिक सुरक्षा सुनिश्चित करने का राष्ट्रीय अभियान।',
    'criteriaEn': 'Families with newborn or girl children below 10 years of age across all districts.',
    'criteriaHi': '10 वर्ष से कम आयु की बालिकाओं वाले सभी भारतीय परिवार।',
    'requiredDocsEn': ['Birth Certificate of Girl Child', 'Parents Aadhaar Card', 'Residence Certificate', 'Bank Account Passbook'],
    'status': 'active',
    'officialUrl': 'https://wcd.nic.in/bbbp-schemes'
  },
  {
    'id': 'SCHEME-SUKANYA-07',
    'titleEn': 'Sukanya Samriddhi Yojana (SSY)',
    'titleHi': 'सुकन्या समृद्धि योजना',
    'ministryEn': 'Ministry of Finance',
    'ministryHi': 'वित्त मंत्रालय',
    'category': 'finance',
    'benefitEn': 'High interest rate of 8.2% p.a. with Section 80C tax exemption for girl child higher education and marriage.',
    'benefitHi': 'बालिका की उच्च शिक्षा हेतु 8.2% वार्षिक ब्याज दर एवं पूर्ण आयकर छूट।',
    'benefitAmount': '8.2% Interest + Tax Benefits',
    'descriptionEn': 'Small deposit scheme for the girl child launched as part of Beti Bachao Beti Padhao campaign.',
    'descriptionHi': 'बालिका की शिक्षा व विवाह हेतु केंद्र सरकार की उच्च बचत योजना।',
    'criteriaEn': 'Parents or legal guardians of a girl child below 10 years of age.',
    'criteriaHi': '10 वर्ष तक की आयु की बालिका के माता-पिता या अभिभावक।',
    'requiredDocsEn': ['Birth Certificate of Child', 'Identity Proof of Guardian (Aadhaar/PAN)', 'Address Proof'],
    'status': 'active',
    'officialUrl': 'https://www.indiapost.gov.in'
  },
  {
    'id': 'SCHEME-SVANIDHI-08',
    'titleEn': "PM Street Vendor's AtmaNirbhar Nidhi (PM SVANidhi)",
    'titleHi': 'पीएम स्वनिधि योजना (स्ट्रीट वेंडर)',
    'ministryEn': 'Ministry of Housing and Urban Affairs',
    'ministryHi': 'आवास एवं शहरी कार्य मंत्रालय',
    'category': 'finance',
    'benefitEn': 'Collateral-free working capital micro-credit: 1st tranche ₹10,000, 2nd tranche ₹20,000, and 3rd tranche up to ₹50,000 with 7% interest subsidy.',
    'benefitHi': 'स्ट्रीट वेंडरों को बिना गारंटी ₹10,000, ₹20,000 और ₹50,000 तक की पूंजी 7% ब्याज सब्सिडी के साथ।',
    'benefitAmount': 'Up to ₹50,000',
    'descriptionEn': 'Special micro-credit facility for urban, peri-urban, and rural street vendors to restart their livelihoods.',
    'descriptionHi': 'सड़क किनारे दुकान लगाने वाले रेहड़ी-पटरी विक्रेताओं के लिए आत्मनिर्भर ऋण योजना।',
    'criteriaEn': 'Street vendors engaged in vending in urban areas on or before March 24, 2020.',
    'criteriaHi': 'शहरी व कस्बाई क्षेत्रों में फेरी लगाने वाले वेंडर जिनके पास वेंडिंग प्रमाण पत्र या सर्वेक्षण पर्ची हो।',
    'requiredDocsEn': ['Aadhaar Card', 'Vending Certificate / Recommendation Letter (LoR)', 'Bank Account Passbook'],
    'status': 'active',
    'officialUrl': 'https://pmsvanidhi.mohua.gov.in'
  },
  {
    'id': 'SCHEME-UJJWALA-09',
    'titleEn': 'Pradhan Mantri Ujjwala Yojana 2.0 (PMUY)',
    'titleHi': 'प्रधानमंत्री उज्ज्वला योजना 2.0',
    'ministryEn': 'Ministry of Petroleum and Natural Gas',
    'ministryHi': 'पेट्रोलियम एवं प्राकृतिक गैस मंत्रालय',
    'category': 'general',
    'benefitEn': 'Deposit-free LPG connection along with free first LPG cylinder and stove, plus ₹300 per cylinder subsidy.',
    'benefitHi': 'मुफ्त गैस कनेक्शन, पहला भरा हुआ गैस सिलेंडर, चूल्हा एवं प्रति सिलेंडर ₹300 की सब्सिडी।',
    'benefitAmount': 'Free Connection + Cylinder Subsidy',
    'descriptionEn': 'Provides clean cooking fuel LPG to women of BPL households to safeguard women\'s health.',
    'descriptionHi': 'गरीब परिवारों की महिलाओं को धुआं-मुक्त रसोई हेतु मुफ्त रसोई गैस कनेक्शन।',
    'criteriaEn': 'Adult woman belonging to poor households without existing LPG connection.',
    'criteriaHi': '18 वर्ष से अधिक आयु की महिला जो बीपीएल या गरीब श्रेणी में हो।',
    'requiredDocsEn': ['Aadhaar Card of Woman', 'Ration Card', 'Bank Passbook', 'Self-declaration Form'],
    'status': 'active',
    'officialUrl': 'https://www.pmuy.gov.in'
  },
  {
    'id': 'SCHEME-ATAL-10',
    'titleEn': 'Atal Pension Yojana (APY)',
    'titleHi': 'अटल पेंशन योजना',
    'ministryEn': 'Ministry of Finance',
    'ministryHi': 'वित्त मंत्रालय',
    'category': 'finance',
    'benefitEn': 'Guaranteed monthly pension of ₹1,000, ₹2,000, ₹3,000, ₹4,000, or ₹5,000 after reaching 60 years of age.',
    'benefitHi': '60 वर्ष की आयु के बाद आजीवन ₹1,000 से ₹5,000 तक की मासिक गारंटीड पेंशन।',
    'benefitAmount': '₹1,000 – ₹5,000 / Month',
    'descriptionEn': 'Government-backed pension scheme aimed at unorganized sector workers for retirement income security.',
    'descriptionHi': 'असंगठित क्षेत्र के कामगारों के लिए वृद्धावस्था पेंशन सुरक्षा योजना।',
    'criteriaEn': 'All Indian citizens aged between 18 to 40 years holding a savings bank account.',
    'criteriaHi': '18 से 40 वर्ष की आयु वाले सभी बचत बैंक खाताधारक नागरिक।',
    'requiredDocsEn': ['Aadhaar Card', 'Savings Bank Account Details', 'Mobile Number'],
    'status': 'active',
    'officialUrl': 'https://www.npscra.nsdl.co.in'
  }
]

# Upsert into MongoDB
for s in schemes:
    schemes_col.update_one({'id': s['id']}, {'$set': s}, upsert=True)

# Write to mock_schemes.json for backend fallback
os.makedirs(os.path.dirname(mock_schemes_path), exist_ok=True)
with open(mock_schemes_path, 'w', encoding='utf-8') as f:
    json.dump(schemes, f, ensure_ascii=False, indent=2)

print(f'Successfully seeded {len(schemes)} schemes into MongoDB and {mock_schemes_path}!')
