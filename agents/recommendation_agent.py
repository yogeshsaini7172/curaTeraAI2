from langchain.messages import HumanMessage
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from dotenv import load_dotenv


# -----------------------------------------
# Environment
# -----------------------------------------

load_dotenv()


# -----------------------------------------
# Model
# -----------------------------------------

model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


# -----------------------------------------
# System Prompt
# -----------------------------------------

system_prompt = """
You are Curaterra's Recommendation Agent.

Your job is to explain the ranked government schemes produced by the recommendation engine.

Rules:

1. Eligibility has already been verified by the eligibility engine.
2. Do not determine or change eligibility.
3. Do not modify, recalculate, or invent ranking scores.
4. Explain the ranking using only the features and scores provided.
5. Do not invent scheme benefits, documents, application details, or other facts.
6. Do not use RAG or web search.
7. Do not claim that a scheme is universally "best" or "most suitable".
8. Instead, say that a scheme is "ranked highest", "more relevant based on the current score", or similar wording.
9. Do not provide application instructions.
10. Keep the response concise and citizen-friendly.
11. Respond in the citizen's language.
12. Only mention information present in the ranking results.

Important:

The recommendation engine calculates the score and ranking.
You only explain the ranking to the citizen.

"""


# -----------------------------------------
# Recommendation Agent
# -----------------------------------------

recommendation_agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    tools=[]
)


# -----------------------------------------
# Response Function
# -----------------------------------------

def get_recommendation_response(input_text: str) -> str:

    response = recommendation_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=input_text
                )
            ]
        }
    )

    return response["messages"][-1].content