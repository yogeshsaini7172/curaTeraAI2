from pathlib import Path
from uuid import uuid4

from flask import request, jsonify
from werkzeug.utils import secure_filename

from ml.opportunity.government_upload import (
    process_uploaded_pdf,
)

# ============================================================
# GOVERNMENT PDF UPLOAD
# ============================================================

@app.post("/api/admin/documents")
def upload_government_document():

    # --------------------------------------------------------
    # IMPORTANT:
    # Replace this with your existing admin-auth check.
    # --------------------------------------------------------

    # Example:
    #
    # if session.get("role") != "admin":
    #     return jsonify({
    #         "status": "error",
    #         "message": "Admin access required."
    #     }), 403

    if "file" not in request.files:

        return jsonify({
            "status": "error",
            "message": "No PDF file uploaded.",
        }), 400

    file = request.files[
        "file"
    ]

    if not file.filename:

        return jsonify({
            "status": "error",
            "message": "Filename is missing.",
        }), 400

    filename = secure_filename(
        file.filename
    )

    if not filename.lower().endswith(
        ".pdf"
    ):

        return jsonify({
            "status": "error",
            "message": "Only PDF files are allowed.",
        }), 400

    upload_dir = Path(
        "data/raw/government_uploads"
    )

    upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    unique_filename = (
        f"{uuid4().hex}_{filename}"
    )

    pdf_path = (
        upload_dir
        / unique_filename
    )

    file.save(
        pdf_path
    )

    try:

        # Replace this with your actual
        # persistent citizen repository.
        citizens = get_active_citizens()

        result = process_uploaded_pdf(
            source_path=pdf_path,
            citizens=citizens,
        )

        return jsonify({
            "status": "success",
            "result": result,
        }), 200

    except Exception as exc:

        return jsonify({
            "status": "error",
            "message": str(exc),
        }), 500