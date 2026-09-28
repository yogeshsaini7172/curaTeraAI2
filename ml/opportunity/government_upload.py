"""
CuraTera AI - Automatic Government PDF Ingestion

Government uploads one PDF.

The system automatically:

    1. validates the PDF
    2. extracts text
    3. identifies the scheme
    4. checks existing/new scheme
    5. processes an existing scheme through Step 10
    6. creates a new scheme when necessary
    7. extracts eligibility rules
    8. checks citizens against a new scheme only
    9. builds opportunities
   10. passes opportunities through existing notification logic

No manual scheme ID is required from the government officer.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field
from pypdf import PdfReader

from langchain_groq import ChatGroq


from ml.eligibility.engine import check_scheme

from ml.opportunity.government_monitor import (
    GovernmentMonitor,
)

from ml.opportunity.opportunity_builder import (
    build_opportunities,
)

from ml.opportunity.notification_decision import (
    decide_notifications,
)

from ml.opportunity.notification_builder import (
    build_notification,
)

from ml.opportunity.scheme_registry import (
    add_eligibility_rules,
    add_new_scheme,
    find_existing_scheme_by_id,
    find_existing_scheme_by_name,
    generate_new_scheme_id,
    load_eligibility_rules,
    normalize_scheme_id,
    scheme_exists,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


UPLOAD_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "government_uploads"
)


VERSION_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "government_versions"
)


MAX_PDF_SIZE_MB = 25


# ============================================================
# STRUCTURED POLICY SCHEMA
# ============================================================

class ExtractedRule(BaseModel):

    rule_id: str

    section: str = "Eligibility"

    attribute: str

    operator: str

    normalized_value: str

    evidence_text: str


class GovernmentPolicy(BaseModel):

    scheme_id: str | None = None

    scheme_name: str

    ministry: str | None = None

    department: str | None = None

    jurisdiction: str | None = None

    description: str | None = None

    source_url: str | None = None

    eligibility_rules: list[
        ExtractedRule
    ] = Field(
        default_factory=list
    )


# ============================================================
# LLM
# ============================================================

structured_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
)

policy_model = structured_llm.with_structured_output(
    GovernmentPolicy,
    method="json_schema",
)


# ============================================================
# PDF VALIDATION
# ============================================================

def validate_pdf(
    pdf_path: Path,
) -> None:

    if not pdf_path.exists():

        raise FileNotFoundError(
            f"PDF does not exist: "
            f"{pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":

        raise ValueError(
            "Only PDF files are supported."
        )

    size_mb = (
        pdf_path.stat().st_size
        / (1024 * 1024)
    )

    if size_mb > MAX_PDF_SIZE_MB:

        raise ValueError(
            f"PDF is larger than "
            f"{MAX_PDF_SIZE_MB} MB."
        )

    try:

        reader = PdfReader(
            str(pdf_path)
        )

        if len(reader.pages) == 0:

            raise ValueError(
                "PDF has no pages."
            )

    except Exception as exc:

        raise ValueError(
            "Uploaded file is not a valid PDF."
        ) from exc


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(
    pdf_path: Path,
) -> str:

    reader = PdfReader(
        str(pdf_path)
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):

        page_text = (
            page.extract_text()
            or ""
        ).strip()

        if page_text:

            pages.append(
                f"\n[PAGE {page_number}]\n"
                f"{page_text}"
            )

    text = "\n".join(
        pages
    ).strip()

    if not text:

        raise ValueError(
            "No readable text was found in the PDF. "
            "This PDF may be scanned and require OCR."
        )

    return text


# ============================================================
# EXPLICIT SCHEME ID
# ============================================================

def extract_scheme_id(
    text: str,
) -> str | None:

    patterns = [

        r"\bSCHEME\s*ID\s*[:\-]?\s*(S\d{1,3})\b",

        r"\bSCHEME\s*CODE\s*[:\-]?\s*(S\d{1,3})\b",

        r"\b(S\d{3})\b",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            value = (
                match.group(1)
                if match.lastindex
                else match.group(0)
            )

            return normalize_scheme_id(
                value
            )

    return None


# ============================================================
# POLICY EXTRACTION
# ============================================================

def extract_policy(
    text: str,
) -> GovernmentPolicy:

    prompt = f"""
You are CuraTera AI's government-policy extraction system.

Extract ONLY information explicitly supported by the
government document below.

Do NOT invent:
- scheme ID
- scheme name
- ministry
- eligibility
- income limits
- age limits
- documents
- benefits
- URLs

Eligibility operators must use only:
==, !=, IN, RANGE, >, >=, <, <=, NO_LIMIT, INFORMATION

Each eligibility rule must include:
- rule_id
- section
- attribute
- operator
- normalized_value
- exact supporting evidence_text

The scheme_id may be null if no official/system scheme ID
appears in the document.

DOCUMENT:

{text}
"""

    result = policy_model.invoke(
        prompt
    )

    return result


# ============================================================
# SAVE UPLOAD
# ============================================================

def save_uploaded_pdf(
    source_path: str | Path,
) -> Path:

    source = Path(
        source_path
    )

    validate_pdf(
        source
    )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    destination = (
        UPLOAD_DIR
        / f"{timestamp}_{source.name}"
    )

    shutil.copy2(
        source,
        destination,
    )

    return destination


# ============================================================
# SAVE IMMUTABLE VERSION
# ============================================================

def save_version(
    scheme_id: str,
    pdf_path: Path,
) -> Path:

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    scheme_dir = (
        VERSION_DIR
        / scheme_id
    )

    scheme_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        scheme_dir
        / f"{timestamp}_{pdf_path.name}"
    )

    shutil.copy2(
        pdf_path,
        destination,
    )

    return destination


# ============================================================
# BUILD NEW SCHEME POLICY
# ============================================================

def ensure_scheme_identity(
    policy: GovernmentPolicy,
) -> tuple[str, bool, str]:

    explicit_id = normalize_scheme_id(
        policy.scheme_id
    )

    # --------------------------------------------------------
    # Existing by explicit ID
    # --------------------------------------------------------

    if explicit_id:

        existing = find_existing_scheme_by_id(
            explicit_id
        )

        if existing:

            return (
                existing["scheme_id"],
                True,
                existing["scheme_name"],
            )

    # --------------------------------------------------------
    # Existing by strong name match
    # --------------------------------------------------------

    existing = find_existing_scheme_by_name(
        policy.scheme_name
    )

    if existing:

        return (
            existing["scheme_id"],
            True,
            existing["scheme_name"],
        )

    # --------------------------------------------------------
    # Completely new scheme
    # --------------------------------------------------------

    new_id = (
        explicit_id
        or generate_new_scheme_id()
    )

    return (
        new_id,
        False,
        policy.scheme_name,
    )


# ============================================================
# PROCESS EXISTING SCHEME
# ============================================================

def process_existing_scheme(
    scheme_id: str,
    scheme_name: str,
    pdf_path: Path,
    citizens: list[dict[str, Any]],
) -> dict[str, Any]:

    version_path = save_version(
        scheme_id=scheme_id,
        pdf_path=pdf_path,
    )

    rules_df = load_eligibility_rules()

    monitor = GovernmentMonitor(
        citizens=citizens,
        rules_df=rules_df,
        source_path=version_path,
        scheme_id=scheme_id,
    )

    result = monitor.run(
        language="en"
    )

    return {
        "status": "existing_scheme_processed",
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "version_path": str(
            version_path
        ),
        "government_result": result,
    }


# ============================================================
# PROCESS NEW SCHEME
# ============================================================

def process_new_scheme(
    scheme_id: str,
    policy: GovernmentPolicy,
    pdf_path: Path,
    citizens: list[dict[str, Any]],
) -> dict[str, Any]:

    # --------------------------------------------------------
    # 1. ADD MASTER SCHEME
    # --------------------------------------------------------

    master_result = add_new_scheme(
        scheme_id=scheme_id,
        scheme_name=policy.scheme_name,
        metadata={
            "ministry": policy.ministry,
            "department": policy.department,
            "description": policy.description,
            "state": policy.jurisdiction,
            "source_url": policy.source_url,
        },
    )

    # --------------------------------------------------------
    # 2. ADD ELIGIBILITY RULES
    # --------------------------------------------------------

    rules_result = add_eligibility_rules(
        scheme_id=scheme_id,
        rules=[
            rule.model_dump()
            for rule in policy.eligibility_rules
        ],
    )

    # --------------------------------------------------------
    # 3. SAVE VERSION
    # --------------------------------------------------------

    version_path = save_version(
        scheme_id=scheme_id,
        pdf_path=pdf_path,
    )

    # --------------------------------------------------------
    # 4. LOAD ONLY NEW SCHEME RULES
    # --------------------------------------------------------

    all_rules = load_eligibility_rules()

    scheme_rules = all_rules[
        all_rules["scheme_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        == scheme_id
    ].copy()

    # --------------------------------------------------------
    # 5. CHECK ALL CITIZENS
    #
    # IMPORTANT:
    # Only the NEW scheme is checked.
    # Existing schemes are NOT rerun.
    # --------------------------------------------------------

    citizen_results = []

    notifications = []

    checked_at = datetime.now(
        timezone.utc
    ).isoformat()

    for citizen in citizens:

        citizen_id = citizen.get(
            "citizen_id",
            "unknown",
        )

        profile = citizen.get(
            "profile",
            {},
        )

        eligibility_result = check_scheme(
            profile=profile,
            scheme_rules=scheme_rules,
        )

        eligibility_result[
            "scheme_id"
        ] = scheme_id

        citizen_results.append(
            {
                "citizen_id": citizen_id,
                "scheme_id": scheme_id,
                "eligibility": (
                    eligibility_result
                ),
            }
        )

        # ----------------------------------------------------
        # Reuse existing opportunity system
        # ----------------------------------------------------

        opportunity_result = (
            build_opportunities(
                citizen_id=citizen_id,
                eligibility_results=[
                    eligibility_result
                ],
                checked_at=checked_at,
            )
        )

        actions = decide_notifications(
            opportunity_result
        )

        for action in actions:

            if action.get("action") != "notify":
                continue

            notifications.append(
                build_notification(
                    citizen_id=citizen_id,
                    scheme_id=scheme_id,
                    opportunity_type=(
                        "new_opportunity"
                    ),
                    language="en",
                    scheme_name=(
                        policy.scheme_name
                    ),
                )
            )

    return {
        "status": "new_scheme_processed",

        "scheme_id": scheme_id,

        "scheme_name": policy.scheme_name,

        "master": master_result,

        "rules": rules_result,

        "version_path": str(
            version_path
        ),

        "citizens_checked": len(
            citizens
        ),

        "citizen_results": citizen_results,

        "notifications": notifications,
    }


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def process_uploaded_pdf(
    source_path: str | Path,
    citizens: list[dict[str, Any]],
) -> dict[str, Any]:

    # --------------------------------------------------------
    # 1. Save upload
    # --------------------------------------------------------

    pdf_path = save_uploaded_pdf(
        source_path
    )

    # --------------------------------------------------------
    # 2. Extract text
    # --------------------------------------------------------

    text = extract_pdf_text(
        pdf_path
    )

    # --------------------------------------------------------
    # 3. Extract policy automatically
    # --------------------------------------------------------

    policy = extract_policy(
        text
    )

    # --------------------------------------------------------
    # 4. Prefer explicit ID from source
    # --------------------------------------------------------

    explicit_id = extract_scheme_id(
        text
    )

    if explicit_id:
        policy.scheme_id = explicit_id

    # --------------------------------------------------------
    # 5. Determine existing/new
    # --------------------------------------------------------

    scheme_id, is_existing, scheme_name = (
        ensure_scheme_identity(
            policy
        )
    )

    # --------------------------------------------------------
    # 6. Existing scheme
    # --------------------------------------------------------

    if is_existing:

        return process_existing_scheme(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            pdf_path=pdf_path,
            citizens=citizens,
        )

    # --------------------------------------------------------
    # 7. New scheme
    # --------------------------------------------------------

    return process_new_scheme(
        scheme_id=scheme_id,
        policy=policy,
        pdf_path=pdf_path,
        citizens=citizens,
    )