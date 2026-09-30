import json
from pathlib import Path

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "demo_identity_records.json"
)

def _normalize(value):
    return str(value or "").strip().lower()

def load_demo_records():
    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)

def verify_demo_identity(
    aadhaar_demo_id: str,
    profile: dict
) -> dict:
    records = load_demo_records()
    record = None
    for item in records:
        if (
            _normalize(
                item.get("aadhaar_demo_id")
            )
            == _normalize(aadhaar_demo_id)
        ):
            record = item
            break

    if record is None:
        return {
            "verified": False,
            "reason": "Demo Aadhaar ID not found.",
            "matched_fields": [],
            "failed_fields": [
                "aadhaar_demo_id"
            ]
        }

    fields_to_check = {
        "name": profile.get("name"),
        "age": profile.get("age"),
        "gender": profile.get("gender"),
        "state": profile.get("state"),
        "district": profile.get("district"),
    }

    matched_fields = []
    failed_fields = []

    for field, profile_value in fields_to_check.items():
        record_value = record.get(field)
        if (
            profile_value is not None
            and record_value is not None
            and _normalize(profile_value)
            == _normalize(record_value)
        ):
            matched_fields.append(field)
        else:
            failed_fields.append(field)

    verified = (
        len(failed_fields) == 0
    )

    return {
        "verified": verified,
        "demo_id": record.get("demo_id"),
        "matched_fields": matched_fields,
        "failed_fields": failed_fields,
        "identity_record": {
            "name": record.get("name"),
            "age": record.get("age"),
            "gender": record.get("gender"),
            "state": record.get("state"),
            "district": record.get("district"),
        }
    }
