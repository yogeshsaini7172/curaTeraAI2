"""
CuraTera AI - Scheme Registry

Responsibilities:
    - Check whether a scheme exists.
    - Match scheme names safely.
    - Add new schemes to scheme_master.csv.
    - Add new eligibility rules to eligibility_rules.csv.
    - Generate internal scheme IDs when an uploaded document
      does not contain an official scheme ID.

This module does NOT:
    - decide eligibility
    - detect policy changes
    - send notifications
"""

from __future__ import annotations

import os
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

SCHEME_MASTER_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "scheme_master.csv"
)

ELIGIBILITY_RULES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "eligibility_rules.csv"
)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_scheme_id(
    value: Any,
) -> str | None:

    if value is None:
        return None

    value = (
        str(value)
        .strip()
        .upper()
    )

    if not value:
        return None

    # 20 -> S020
    if value.isdigit():
        return f"S{int(value):03d}"

    # S20 -> S020
    if value.startswith("S"):

        number = value[1:]

        if number.isdigit():
            return f"S{int(number):03d}"

    return value


def normalize_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    value = (
        str(value)
        .strip()
        .lower()
    )

    return " ".join(
        value.split()
    )


# ============================================================
# ATOMIC CSV WRITE
# ============================================================

def atomic_write_csv(
    df: pd.DataFrame,
    path: Path,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, temp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )

    os.close(fd)

    temp_path = Path(
        temp_name
    )

    try:

        df.to_csv(
            temp_path,
            index=False,
        )

        os.replace(
            temp_path,
            path,
        )

    except Exception:

        if temp_path.exists():
            temp_path.unlink()

        raise


# ============================================================
# LOAD MASTER
# ============================================================

def load_scheme_master() -> pd.DataFrame:

    if not SCHEME_MASTER_PATH.exists():

        raise FileNotFoundError(
            f"Missing scheme master: "
            f"{SCHEME_MASTER_PATH}"
        )

    return pd.read_csv(
        SCHEME_MASTER_PATH
    )


def load_eligibility_rules() -> pd.DataFrame:

    if not ELIGIBILITY_RULES_PATH.exists():

        raise FileNotFoundError(
            f"Missing eligibility rules: "
            f"{ELIGIBILITY_RULES_PATH}"
        )

    return pd.read_csv(
        ELIGIBILITY_RULES_PATH
    )


# ============================================================
# FIND COLUMN
# ============================================================

def find_column(
    columns,
    aliases: list[str],
    required: bool = True,
) -> str | None:

    lookup = {
        normalize_text(column): column
        for column in columns
    }

    for alias in aliases:

        found = lookup.get(
            normalize_text(alias)
        )

        if found:
            return found

    if required:

        raise ValueError(
            "Required column not found. "
            f"Expected one of: {aliases}"
        )

    return None


# ============================================================
# CHECK EXISTING SCHEME
# ============================================================

def find_existing_scheme_by_id(
    scheme_id: str,
) -> dict[str, Any] | None:

    scheme_id = normalize_scheme_id(
        scheme_id
    )

    if not scheme_id:
        return None

    df = load_scheme_master()

    id_column = find_column(
        df.columns,
        [
            "scheme_id",
            "scheme id",
            "id",
        ],
    )

    name_column = find_column(
        df.columns,
        [
            "scheme_name",
            "scheme name",
            "name",
            "scheme",
        ],
        required=False,
    )

    ids = (
        df[id_column]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    matches = df[
        ids == scheme_id
    ]

    if matches.empty:
        return None

    row = matches.iloc[0]

    return {
        "scheme_id": scheme_id,
        "scheme_name": (
            str(
                row[name_column]
            )
            if name_column
            else scheme_id
        ),
        "match_type": "exact_id",
    }


# ============================================================
# NAME MATCHING
# ============================================================

def find_existing_scheme_by_name(
    scheme_name: str,
    threshold: float = 0.88,
) -> dict[str, Any] | None:

    if not scheme_name:
        return None

    df = load_scheme_master()

    id_column = find_column(
        df.columns,
        [
            "scheme_id",
            "scheme id",
            "id",
        ],
    )

    name_column = find_column(
        df.columns,
        [
            "scheme_name",
            "scheme name",
            "name",
            "scheme",
        ],
    )

    target = normalize_text(
        scheme_name
    )

    best_score = 0.0
    best_row = None

    for _, row in df.iterrows():

        existing_name = normalize_text(
            row[name_column]
        )

        if not existing_name:
            continue

        score = SequenceMatcher(
            None,
            target,
            existing_name,
        ).ratio()

        if score > best_score:

            best_score = score
            best_row = row

    if (
        best_row is not None
        and best_score >= threshold
    ):

        return {
            "scheme_id": normalize_scheme_id(
                best_row[id_column]
            ),
            "scheme_name": str(
                best_row[name_column]
            ),
            "match_type": "name_similarity",
            "match_score": round(
                best_score,
                4,
            ),
        }

    return None


# ============================================================
# GENERATE INTERNAL ID
# ============================================================

def generate_new_scheme_id() -> str:

    df = load_scheme_master()

    id_column = find_column(
        df.columns,
        [
            "scheme_id",
            "scheme id",
            "id",
        ],
    )

    numbers = []

    for value in df[id_column]:

        normalized = (
            normalize_scheme_id(value)
        )

        if not normalized:
            continue

        if normalized.startswith("S"):

            number = normalized[1:]

            if number.isdigit():
                numbers.append(
                    int(number)
                )

    next_number = (
        max(numbers) + 1
        if numbers
        else 1
    )

    return f"S{next_number:03d}"


# ============================================================
# ADD NEW SCHEME
# ============================================================

def add_new_scheme(
    scheme_id: str,
    scheme_name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:

    metadata = metadata or {}

    scheme_id = normalize_scheme_id(
        scheme_id
    )

    if not scheme_id:
        raise ValueError(
            "scheme_id is required."
        )

    if not scheme_name:
        raise ValueError(
            "scheme_name is required."
        )

    df = load_scheme_master()

    id_column = find_column(
        df.columns,
        [
            "scheme_id",
            "scheme id",
            "id",
        ],
    )

    name_column = find_column(
        df.columns,
        [
            "scheme_name",
            "scheme name",
            "name",
            "scheme",
        ],
    )

    ids = (
        df[id_column]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if scheme_id in set(ids):

        return {
            "created": False,
            "scheme_id": scheme_id,
            "reason": "already_exists",
        }

    # Preserve existing CSV schema.
    new_row = {
        column: ""
        for column in df.columns
    }

    new_row[id_column] = scheme_id
    new_row[name_column] = scheme_name.strip()

    # Optional fields.
    mappings = {
        "ministry": [
            "ministry",
            "ministry_name",
        ],
        "department": [
            "department",
            "department_name",
        ],
        "description": [
            "description",
            "scheme_description",
        ],
        "state": [
            "state",
            "jurisdiction",
        ],
        "category": [
            "category",
            "scheme_category",
        ],
        "source_url": [
            "source_url",
            "official_url",
            "source",
        ],
    }

    for metadata_key, aliases in mappings.items():

        value = metadata.get(
            metadata_key
        )

        if value is None:
            continue

        column = find_column(
            df.columns,
            aliases,
            required=False,
        )

        if column:
            new_row[column] = value

    updated = pd.concat(
        [
            df,
            pd.DataFrame([new_row]),
        ],
        ignore_index=True,
    )

    atomic_write_csv(
        updated,
        SCHEME_MASTER_PATH,
    )

    return {
        "created": True,
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
    }


# ============================================================
# ADD RULES
# ============================================================

def add_eligibility_rules(
    scheme_id: str,
    rules: list[dict[str, Any]],
) -> dict[str, Any]:

    scheme_id = normalize_scheme_id(
        scheme_id
    )

    if not scheme_id:
        raise ValueError(
            "scheme_id is required."
        )

    df = load_eligibility_rules()

    required_columns = [
        "scheme_id",
        "rule_id",
        "section",
        "attribute",
        "operator",
        "normalized_value",
        "evidence_text",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "eligibility_rules.csv missing "
            f"columns: {missing}"
        )

    existing_rule_ids = set(
        df["rule_id"]
        .astype(str)
        .str.strip()
    )

    new_rows = []

    for rule in rules:

        rule_id = str(
            rule.get(
                "rule_id",
                "",
            )
        ).strip()

        if not rule_id:
            raise ValueError(
                "Each rule requires rule_id."
            )

        if rule_id in existing_rule_ids:
            continue

        new_rows.append(
            {
                "scheme_id": scheme_id,
                "rule_id": rule_id,
                "section": rule.get(
                    "section",
                    "Eligibility",
                ),
                "attribute": rule.get(
                    "attribute",
                    "",
                ),
                "operator": str(
                    rule.get(
                        "operator",
                        "",
                    )
                ).strip().upper(),
                "normalized_value": rule.get(
                    "normalized_value",
                    "",
                ),
                "evidence_text": rule.get(
                    "evidence_text",
                    "",
                ),
            }
        )

    if not new_rows:

        return {
            "created": False,
            "scheme_id": scheme_id,
            "rules_added": 0,
        }

    updated = pd.concat(
        [
            df,
            pd.DataFrame(new_rows),
        ],
        ignore_index=True,
    )

    atomic_write_csv(
        updated,
        ELIGIBILITY_RULES_PATH,
    )

    return {
        "created": True,
        "scheme_id": scheme_id,
        "rules_added": len(new_rows),
    }