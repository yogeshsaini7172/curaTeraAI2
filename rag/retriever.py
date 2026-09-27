from pathlib import Path
from functools import lru_cache

from langchain_community.vectorstores import FAISS

from rag.embeddings import get_embeddings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_PATH = PROJECT_ROOT / "vectorstore"


@lru_cache(maxsize=1)
def load_vectorstore():
    """
    Load FAISS only once and reuse it.
    """

    if not VECTORSTORE_PATH.exists():
        try:
            print(f"[RETRIEVER] Vector store not found at {VECTORSTORE_PATH}. Attempting to build automatically...")
            from rag.build_vectorstore import build_vectorstore
            build_vectorstore()
        except Exception as e:
            raise FileNotFoundError(
                f"Vector store not found at {VECTORSTORE_PATH} and auto-build failed: {e}"
            )

    if not VECTORSTORE_PATH.exists():
        raise FileNotFoundError(
            f"Vector store not found: {VECTORSTORE_PATH}"
        )

    embeddings = get_embeddings()

    vectorstore = FAISS.load_local(
        str(VECTORSTORE_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )

    return vectorstore


def retrieve_documents(
    query: str,
    k: int = 10,
    scheme_id: str | None = None,
    sections: list[str] | None = None
):
    vectorstore = load_vectorstore()

    # -----------------------------------------------------
    # Retrieve by scheme
    # -----------------------------------------------------

    if scheme_id:

        fetch_k = vectorstore.index.ntotal

        documents = vectorstore.similarity_search(
            query,
            k=k,
            fetch_k=fetch_k,
            filter={
                "scheme_id": scheme_id
            }
        )

    else:

        documents = vectorstore.similarity_search(
            query,
            k=k
        )

    # -----------------------------------------------------
    # Section filtering
    # -----------------------------------------------------

    if sections:

        wanted_sections = {
            section.strip().lower()
            for section in sections
        }

        section_documents = [
            doc
            for doc in documents
            if str(
                doc.metadata.get("section", "")
            ).strip().lower()
            in wanted_sections
        ]

        # Only replace the result if matching
        # section documents were actually found.
        if section_documents:
            documents = section_documents

    print(
        f"\n[RETRIEVER] "
        f"query={query!r} "
        f"scheme_id={scheme_id!r} "
        f"sections={sections!r} "
        f"returned={len(documents)}"
    )

    for doc in documents:

        print(
            "[RETRIEVER]",
            doc.metadata.get("scheme_id"),
            doc.metadata.get("section"),
            doc.metadata.get("chunk_id")
        )

    return documents