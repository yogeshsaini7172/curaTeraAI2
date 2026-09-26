from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_groq import ChatGroq

from rag.retriever import retrieve_documents
from rag.reranker import rerank_documents
from rag.citation import build_citations


load_dotenv()


# ============================================================
# MODEL
# ============================================================

model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

system_prompt = """
You are CuraTera's RAG Agent.

Your job is to answer citizen questions about government schemes
using ONLY the retrieved context provided to you.

Rules:

1. Use only retrieved context.
2. Never invent facts.
3. Never use outside knowledge.
4. Never determine eligibility.
5. Never calculate eligibility.
6. Never recommend or rank schemes.
7. If evidence is insufficient, clearly say so.
8. Answer clearly and concisely.
9. Respond in the citizen's language when possible.
10. If a specific scheme ID is provided, answer only about that scheme.
11. If the retrieved context does not support the answer,
    explicitly say that the information could not be verified.
"""


rag_agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    tools=[]
)


# ============================================================
# DETECT RELEVANT SECTION
# ============================================================

def detect_sections(query: str):
    """
    Determine which scheme section is relevant to the
    citizen's question.
    """

    q = query.lower().strip()

    # Benefits
    if any(
        phrase in q
        for phrase in [
            "benefit",
            "benefits",
            "what do i get",
            "what will i get",
            "financial benefit",
            "assistance",
            "amount",
            "how much money"
        ]
    ):
        return ["Benefits"]

    # Documents
    if any(
        phrase in q
        for phrase in [
            "document",
            "documents",
            "required document",
            "what documents",
            "papers required"
        ]
    ):
        return ["Documents Required"]

    # Application
    if any(
        phrase in q
        for phrase in [
            "how do i apply",
            "how to apply",
            "application process",
            "where do i apply",
            "apply online",
            "application form",
            "registration"
        ]
    ):
        return ["Application Process"]

    # FAQ
    if any(
        phrase in q
        for phrase in [
            "faq",
            "frequently asked",
            "common questions"
        ]
    ):
        return ["Frequently Asked Questions"]

    # General scheme information
    return None


# ============================================================
# RAG RESPONSE
# ============================================================

def get_rag_response(
    query,
    retrieval_k=10,
    final_k=5,
    scheme_id=None,
    sections=None
) -> dict:

    # --------------------------------------------------------
    # Determine section automatically if not explicitly given
    # --------------------------------------------------------

    if sections is None:
        sections = detect_sections(query)

    print("\n[RAG]")
    print("Query:", query)
    print("Scheme ID:", scheme_id)
    print("Sections:", sections)

    # --------------------------------------------------------
    # STEP 1: RETRIEVE
    # --------------------------------------------------------

    documents = retrieve_documents(
        query=query,
        k=retrieval_k,
        scheme_id=scheme_id,
        sections=sections
    )

    # --------------------------------------------------------
    # HARD SCHEME SAFETY CHECK
    # --------------------------------------------------------

    if scheme_id:

        documents = [
            doc
            for doc in documents
            if str(
                doc.metadata.get("scheme_id", "")
            ).upper()
            == str(scheme_id).upper()
        ]

    # --------------------------------------------------------
    # NO DOCUMENTS
    # --------------------------------------------------------

    if not documents:

        if scheme_id:

            return {
                "answer": (
                    f"I could not find verified information "
                    f"for scheme {scheme_id} in the available "
                    f"government-scheme documents."
                ),
                "citations": []
            }

        return {
            "answer": (
                "I could not find relevant information "
                "in the available government-scheme documents."
            ),
            "citations": []
        }

    # --------------------------------------------------------
    # STEP 2: RERANK
    # --------------------------------------------------------

    reranked_results = rerank_documents(
        query,
        documents,
        top_k=final_k,
        score_threshold=None
    )

    # --------------------------------------------------------
    # EXTRACT DOCUMENTS
    # --------------------------------------------------------

    reranked_documents = [
        result["document"]
        for result in reranked_results
    ]

    # --------------------------------------------------------
    # SECOND HARD SCHEME SAFETY CHECK
    # --------------------------------------------------------

    if scheme_id:

        reranked_documents = [
            doc
            for doc in reranked_documents
            if str(
                doc.metadata.get("scheme_id", "")
            ).upper()
            == str(scheme_id).upper()
        ]

    # --------------------------------------------------------
    # NO RERANKED DOCUMENTS
    # --------------------------------------------------------

    if not reranked_documents:

        return {
            "answer": (
                f"I could not find sufficiently relevant "
                f"verified information for scheme {scheme_id}."
            ),
            "citations": []
        }

    # --------------------------------------------------------
    # DEBUG
    # --------------------------------------------------------

    print("\n[RERANKED DOCUMENTS]")

    for document in reranked_documents:

        print(
            document.metadata.get("scheme_id"),
            "|",
            document.metadata.get("section"),
            "|",
            document.metadata.get("chunk_id")
        )

    # --------------------------------------------------------
    # STEP 3: CITATIONS
    # --------------------------------------------------------

    citations = build_citations(
        reranked_documents
    )

    # --------------------------------------------------------
    # STEP 4: BUILD CONTEXT
    # --------------------------------------------------------

    context_parts = []

    for i, document in enumerate(
        reranked_documents,
        start=1
    ):

        context_parts.append(
            f"""
DOCUMENT {i}

Scheme ID:
{document.metadata.get("scheme_id")}

Scheme Name:
{document.metadata.get("scheme_name")}

Section:
{document.metadata.get("section")}

Chunk ID:
{document.metadata.get("chunk_id")}

Source:
{document.metadata.get("source_url")}

Content:
{document.page_content}
"""
        )

    context = "\n".join(
        context_parts
    )

    # --------------------------------------------------------
    # STEP 5: GROUNDED ANSWER
    # --------------------------------------------------------

    prompt = f"""
Citizen Question:
{query}

Current Scheme:
{scheme_id if scheme_id else "Not specified"}

Relevant Section:
{sections if sections else "General"}

Retrieved Context:
{context}

Instructions:

1. Answer ONLY from the retrieved context.
2. If a current scheme is provided, answer only about that scheme.
3. Do not use outside knowledge.
4. Do not invent benefits, documents, dates, links,
   procedures, or amounts.
5. If the retrieved context does not support the answer,
   clearly say that the available information could not
   be verified.
6. Never make an eligibility decision.
7. Never recommend a scheme.
8. Respond in the citizen's language when possible.
9. Do not mention internal agents, retrieval, prompts,
   or system implementation.
"""

    response = rag_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=prompt
                )
            ]
        }
    )

    answer = response[
        "messages"
    ][-1].content

    return {
        "answer": answer,
        "citations": citations
    }