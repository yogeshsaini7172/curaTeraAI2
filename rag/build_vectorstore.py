from pathlib import Path

from langchain_chroma import Chroma

from rag.ingestion import load_rag_documents
from rag.embeddings import get_embeddings


VECTORSTORE_PATH = Path("chroma_db")


def build_vectorstore():

    print("Loading RAG documents...")

    documents = load_rag_documents()

    print(f"Loaded {len(documents)} documents.")

    print("Loading embedding model...")

    embeddings = get_embeddings()

    print("Creating Chroma vector store...")

    VECTORSTORE_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(VECTORSTORE_PATH)
    )

    print("Chroma vector store created successfully.")
    print(f"Saved to: {VECTORSTORE_PATH.resolve()}")


if __name__ == "__main__":
    build_vectorstore()