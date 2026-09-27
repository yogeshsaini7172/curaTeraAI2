from pathlib import Path
import json

from langchain_core.documents import Document


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAG_DOCUMENTS_PATH = PROJECT_ROOT / "data" / "rag" / "rag_documents.json"


# --------------------------------------------------
# Load RAG JSON
# --------------------------------------------------

def load_rag_documents(
    file_path: str | Path = RAG_DOCUMENTS_PATH
) -> list[Document]:
    """
    Load the processed RAG JSON file and convert
    each record into a LangChain Document.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"RAG document file not found: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "rag_documents.json must contain a list of records."
        )

    documents = []

    for item in data:

        if not isinstance(item, dict):
            continue

        text = item.get("text")

        if not text or not str(text).strip():
            continue

        metadata = {
            "scheme_id": item.get("scheme_id"),
            "scheme_name": item.get("scheme_name"),
            "section": item.get("section"),
            "chunk_id": item.get("chunk_id"),
            "source_file": item.get("source_file"),
            "source_start_line": item.get("source_start_line"),
            "source_url": item.get("source_url"),
        }

        document = Document(
            page_content=str(text).strip(),
            metadata=metadata
        )

        documents.append(document)

    return documents