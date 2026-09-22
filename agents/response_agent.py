# agents/response_agent.py

from typing import Any

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv


load_dotenv()


# =========================================================
# 1. STRUCTURED RESPONSE SCHEMA
# =========================================================

class ResponseBlock(BaseModel):
    type: str
    data: dict[str, Any] = Field(
        default_factory=dict
    )


class ResponseEnvelope(BaseModel):
    message: str
    blocks: list[ResponseBlock] = Field(
        default_factory=list
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list
    )
    profile: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


# =========================================================
# 2. LLM MESSAGE SCHEMA
# =========================================================

class ResponseMessage(BaseModel):
    message: str = Field(
        description="Final citizen-facing response."
    )


# =========================================================
# 3. MODEL
# =========================================================

model = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


# Use strict JSON schema output so the model must follow
# the ResponseMessage schema.
structured_model = model.with_structured_output(
    ResponseMessage,
    method="json_schema",
    strict=True
)


# =========================================================
# 4. TASK INSTRUCTIONS
# =========================================================

TASK_INSTRUCTIONS = {
    " Listen use Emoji's as needed in creating the final resposne okay soo that it should look like user friendly view right"
    # ========================================================
    # ELIGIBILITY
    # ========================================================

    "eligibility": """
Your task is to explain the eligibility result produced by
CuraTera's deterministic eligibility engine.

The eligibility engine is the ONLY source of truth for
eligibility.

You MUST:
- Preserve the exact status: eligible, not_eligible,
  or missing_information.
- Never recalculate eligibility yourself.
- Never change or reinterpret the eligibility decision.
- Explain the main reasons for the result.
- Mention important failed conditions when available.
- Mention missing information when available.
- Clearly distinguish between conditions that were passed,
  failed, and not yet evaluated because information is missing.
- Never invent eligibility requirements.
- Never claim guaranteed approval.

Response style:
- Start with the result.
- Then briefly explain why.
- Use bullets when multiple conditions need to be explained.
- Keep the explanation easy for an ordinary citizen to understand.
""",

    # ========================================================
    # RECOMMENDATION
    # ========================================================

    "recommendation": """
Your task is to explain recommendations produced by
CuraTera's recommendation system.

The recommendation system is the source of truth for ranking.

You MUST:
- Preserve the exact ranking supplied by the system.
- Do not create your own ranking.
- Explain why the recommended schemes match the citizen
  using the supplied profile and recommendation information.
- Mention the strongest matches first according to the
  supplied ranking.
- Clearly state that a recommendation does not guarantee
  eligibility, approval, or benefit receipt.
- Never invent scheme benefits or eligibility conditions.

Response style:
- Start with a brief overall recommendation.
- Present recommended schemes clearly.
- Give a short reason for each relevant recommendation.
- Use numbered or bullet lists when there are multiple schemes.
""",

    # ========================================================
    # RAG / SCHEME INFORMATION
    # ========================================================

    "rag": """
Your task is to answer the citizen's scheme-information
question using retrieved government information.

The retrieved information is the source of truth for
scheme-specific facts.

You MUST:
- Answer the user's actual question directly.
- Use only information supplied by retrieval.
- Prefer official-source information when provided.
- Never invent benefits, amounts, rules, coverage, deadlines,
  documents, or other scheme facts.
- Do not infer facts that are not supported by the retrieved
  information.
- When the retrieved information is insufficient, clearly say
  that the available information does not establish the answer.
- Preserve citations when they are supplied.

Response style:
- Give the direct answer first.
- Organize information with headings or bullets when useful.
- Avoid unnecessarily repeating the retrieved text.
- Keep the answer focused on the user's question.
""",

    # ========================================================
    # APPLICATION
    # ========================================================

    "application": """
Your task is to explain how the citizen can apply for the
specified government scheme using verified application
information.

The supplied application information is the source of truth.

You MUST:
- Use only supplied application information.
- Explain the application process in the correct order.
- Mention required documents when supplied.
- Mention the official application channel or portal only
  when supplied.
- Never invent application portals, URLs, deadlines, fees,
  documents, or procedures.
- If an important application detail is not available,
  clearly state that it was not found in the supplied
  information.
- Preserve citations when supplied.

Response style:
- Use numbered steps for the application process.
- Separate application steps from required documents when
  useful.
- Make the answer practical and easy to follow.
""",

    # ========================================================
    # PROFILE
    # ========================================================

    "profile": """
Your task is to communicate profile-related information to
the citizen.

The stored citizen profile is the source of truth.

You MUST:
- Preserve information already provided by the citizen.
- Never invent personal information.
- Clearly identify information that is still missing.
- Ask only for information that is actually needed.
- Do not repeatedly ask for information that is already present.
- When correcting a profile field, acknowledge the correction
  clearly.

Response style:
- Be conversational and friendly.
- Ask concise questions for missing information.
- Do not overwhelm the citizen with a long list unless many
  required fields are actually missing.
""",

    # ========================================================
    # GENERAL
    # ========================================================

    "general": """
Your task is normal conversation with the citizen.

You MUST:
- Understand the user's current message in context.
- Respond naturally and helpfully.
- Handle greetings, thanks, acknowledgements, and casual
  conversation naturally.
- Answer general questions when they are within your allowed
  scope.
- Do not invent government-scheme facts.
- Do not make eligibility decisions.
- Do not invent benefits, documents, deadlines, or application
  procedures.

Response style:
- Conversational.
- Clear.
- Concise for simple questions.
- More detailed only when the user asks for explanation.
""",

    # ========================================================
    # CLARIFICATION
    # ========================================================

    "clarification": """
Your task is to ask for the missing context required to answer
a scheme-specific question safely.

Use this task when the citizen refers to a scheme but no scheme
has been identified.

You MUST:
- Clearly state that the scheme needs to be identified.
- Ask for the scheme ID or scheme name.
- Give a simple example such as S020 or S039.
- Never guess which scheme the citizen means.
- Do not provide information about an unknown scheme.

Response style:
- Very concise.
- Helpful rather than technical.
""",

    # ========================================================
    # MULTIPLE TASKS
    # ========================================================

    "multi": """
Your task is to combine results from multiple CuraTera
specialists into one coherent answer.

You may receive results from:
- eligibility
- recommendation
- RAG
- application

You MUST:
- Answer every part of the citizen's question.
- Preserve the meaning of every supplied specialist result.
- Never change an eligibility decision.
- Preserve recommendation ranking.
- Use only supplied RAG/application information for
  scheme-specific facts.
- Never invent missing information.
- Avoid repeating the same information multiple times.
- Present related information together.
- Preserve citations when supplied.
- Do not mention internal agents, planners, tools, or
  implementation details.

Response style:
- Read naturally as one answer.
- Use headings, numbered steps, or bullets when they improve
  clarity.
- Prioritize the user's most important question first.
"""
}


# =========================================================
# 5. GENERATE NATURAL-LANGUAGE MESSAGE
# =========================================================

def generate_message(
    task: str,
    user_query: str,
    specialist_result: Any,
    profile: dict[str, Any] | None = None,
    scheme_id: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    language: str = "English",
    messages: list[dict] | None = None
) -> str:

    task_instruction = TASK_INSTRUCTIONS.get(
        task,
        TASK_INSTRUCTIONS["general"]
    )

    system_prompt = f"""
You are the Response Generator Agent for CuraTera AI. and most important use emoji's as neede in the situtaion okay for user friendly answer right

Your job is to explain a verified result to a citizen.

You are the final communication layer between
CuraTera's internal systems and the citizen.

IMPORTANT:
- You are not the decision maker.
- You must not modify specialist results.
- You must not invent information.
- Use simple, professional, citizen-friendly language.
- Answer in {language}.
- Answer the user's actual question.
- Use the supplied conversation context and profile when relevant.
- Do not expose internal implementation details.

TASK:
{task}

TASK-SPECIFIC INSTRUCTIONS:
{task_instruction}

Before generating the response:
1. Understand the user's immediate question.
2. Understand the task.
3. Inspect the supplied specialist result.
4. Use profile and scheme context when relevant.
5. Preserve verified facts exactly.
6. Decide the clearest way to present the information.
7. Generate only the final citizen-facing response.
"""

    messages_context = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages]) if messages else "None"

    human_prompt = f"""
RECENT CONVERSATION HISTORY:
{messages_context}

USER QUERY:
{user_query}

CITIZEN PROFILE:
{profile}

CURRENT SCHEME:
{scheme_id}

VERIFIED SPECIALIST RESULT:
{specialist_result}

AVAILABLE CITATIONS:
{citations or []}

Generate only the final citizen-facing message.
"""

    try:

        response = structured_model.invoke(
            [
                SystemMessage(
                    content=system_prompt
                ),
                HumanMessage(
                    content=human_prompt
                )
            ]
        )

        return response.message

    except Exception as error:

        print(
            "\n[RESPONSE AGENT WARNING]",
            error
        )

        # Safe fallback.
        if task == "profile":

            return (
                "I’ve updated your profile with the "
                "information you provided. "
                "Please share any remaining details "
                "needed to complete your profile."
            )

        if task == "clarification":

            return (
                "Please provide the government scheme "
                "ID or scheme name so I can help you."
            )

        return (
            "I’m sorry, I couldn't generate the response "
            "right now. Please try again."
        )


# =========================================================
# 6. DETERMINISTIC BLOCK CREATION
# =========================================================

def build_blocks(
    task: str,
    specialist_result: Any
) -> list[ResponseBlock]:

    blocks = []

    # --------------------------------------------------------
    # Eligibility
    # --------------------------------------------------------

    if task == "eligibility":

        if not isinstance(
            specialist_result,
            list
        ):
            specialist_result = [
                specialist_result
            ]

        eligible_count = 0
        not_eligible_count = 0
        missing_count = 0

        for result in specialist_result:

            if not isinstance(
                result,
                dict
            ):
                continue

            scheme_id = result.get(
                "scheme_id"
            )

            status = result.get(
                "status"
            )

            if status == "eligible":
                eligible_count += 1

            elif status == "not_eligible":
                not_eligible_count += 1

            elif status == "missing_information":
                missing_count += 1

            blocks.append(
                ResponseBlock(
                    type="eligibility_summary",
                    data={
                        "scheme_id": scheme_id,
                        "status": status
                    }
                )
            )

            failed_rules = result.get(
                "failed_rules",
                []
            )

            for rule in failed_rules:

                blocks.append(
                    ResponseBlock(
                        type="failed_condition",
                        data={
                            "scheme_id": scheme_id,
                            "attribute": rule.get(
                                "attribute"
                            ),
                            "actual": rule.get(
                                "actual"
                            ),
                            "operator": rule.get(
                                "operator"
                            ),
                            "expected": rule.get(
                                "expected"
                            )
                        }
                    )
                )

            missing_information = result.get(
                "missing_information",
                []
            )

            if missing_information:

                blocks.append(
                    ResponseBlock(
                        type="missing_information",
                        data={
                            "scheme_id": scheme_id,
                            "fields": missing_information
                        }
                    )
                )

        blocks.insert(
            0,
            ResponseBlock(
                type="eligibility_overview",
                data={
                    "eligible_count": eligible_count,
                    "not_eligible_count": not_eligible_count,
                    "missing_information_count": missing_count
                }
            )
        )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    elif task == "recommendation":

        if isinstance(
            specialist_result,
            list
        ):

            for rank, item in enumerate(
                specialist_result,
                start=1
            ):

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                blocks.append(
                    ResponseBlock(
                        type="recommendation",
                        data={
                            "rank": rank,
                            "scheme_id": item.get(
                                "scheme_id"
                            ),
                            "score": item.get(
                                "score"
                            )
                        }
                    )
                )

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    elif task == "rag":

        if isinstance(
            specialist_result,
            dict
        ):

            result_scheme_id = specialist_result.get(
                "scheme_id"
            )

            if result_scheme_id:

                blocks.append(
                    ResponseBlock(
                        type="scheme_card",
                        data={
                            "scheme_id": result_scheme_id
                        }
                    )
                )

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    elif task == "application":

        blocks.append(
            ResponseBlock(
                type="application_steps",
                data={}
            )
        )

    return blocks


# =========================================================
# 7. MAIN RESPONSE FUNCTION
# =========================================================

def generate_response(
    task: str,
    user_query: str,
    specialist_result: Any,
    profile: dict[str, Any] | None = None,
    scheme_id: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    language: str = "English",
    messages: list[dict] | None = None
) -> ResponseEnvelope:

    # --------------------------------------------------------
    # Generate natural-language answer
    # --------------------------------------------------------

    message = generate_message(
        task=task,
        user_query=user_query,
        specialist_result=specialist_result,
        profile=profile,
        scheme_id=scheme_id,
        citations=citations,
        language=language,
        messages=messages
    )

    # --------------------------------------------------------
    # Create deterministic blocks
    # --------------------------------------------------------

    blocks = build_blocks(
        task=task,
        specialist_result=specialist_result
    )

    # --------------------------------------------------------
    # Build metadata
    # --------------------------------------------------------

    metadata = {
        "intent": task,
        "scheme_id": scheme_id,
        "language": language
    }

    # --------------------------------------------------------
    # Return final envelope
    # --------------------------------------------------------

    return ResponseEnvelope(
        message=message,
        blocks=blocks,
        citations=citations or [],
        profile=profile,
        metadata=metadata
    )