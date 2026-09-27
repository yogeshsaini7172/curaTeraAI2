from pathlib import Path

from langchain_community.vectorstores import FAISS

from rag.ingestion import load_rag_documents
from rag.embeddings import get_embeddings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_PATH = PROJECT_ROOT / "vectorstore"


def build_vectorstore():

    print("Loading RAG documents...")

    documents = load_rag_documents()

    print(f"Loaded {len(documents)} documents.")

    print("Loading embedding model...")

    embeddings = get_embeddings()

    print("Creating FAISS vector store...")

    vectorstore = FAISS.from_documents(
        documents,
        embeddings
    )

    VECTORSTORE_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    vectorstore.save_local(
        str(VECTORSTORE_PATH)
    )

    print("FAISS vector store created successfully.")
    print(f"Saved to: {VECTORSTORE_PATH.resolve()}")


if __name__ == "__main__":
    build_vectorstore()