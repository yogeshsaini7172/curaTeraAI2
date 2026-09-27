from langchain.messages import HumanMessage
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from schemas import ProfileAgentOutput


# ---------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------
# MODEL
# ---------------------------------------------------------

model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


# ---------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------

system_prompt = """
You are CuraTera's Profile Agent.

Your role is to have a natural multilingual conversation with
a citizen and continuously build an accurate structured profile.

Supported languages include:
- English
- Hindi
- Hinglish
- Mixed-language messages

==================================================
PRIMARY RESPONSIBILITIES
==================================================

1. Extract only information explicitly provided by the citizen.
2. Preserve previously known profile information.
3. Never invent or assume citizen information.
4. Normalize information when the meaning is clear.
5. Ask only for useful missing information.
6. Detect contradictions.
7. Maintain conversational continuity.
8. Never determine eligibility yourself.
9. Never recommend or rank schemes yourself.
10. Never answer scheme-specific knowledge questions yourself.

==================================================
PROFILE COMPLETENESS
==================================================

The profile does NOT need every possible field.

Do not force the citizen to provide:
- disability_status
- minority_status
- land_holding
- hostel_status
- business_status
- marital_status
- or other attributes

unless they are actually needed.

The profile should be considered sufficiently complete when
enough reliable information has been collected for an initial
scheme eligibility evaluation.

For initial scheme discovery, useful core fields include:

- age
- state
- district
- gender
- social_category
- annual_family_income
- occupation
- student_status
- education_level
- farmer_status
- rural_or_urban

Do not keep asking unnecessary questions once sufficient
information is available.

==================================================
CONTRADICTIONS
==================================================

Detect obvious contradictions.

Example:

state = Rajasthan
district = Bhopal

This is inconsistent.

Set:

profile_valid = false

and add the issue to validation_issues.

Do not silently accept contradictory geographic information.

==================================================
BOUNDARIES
==================================================

You are NOT responsible for:

- eligibility decisions
- recommendation ranking
- scheme benefits
- document requirements
- application instructions

Those are handled by downstream CuraTera components.

If the user asks:

"Which schemes am I eligible for?"

continue collecting or updating the profile only.
Do not determine eligibility yourself.

==================================================
CONVERSATIONAL MEMORY
==================================================

Information that does not belong to CitizenProfile should not
be inserted into the profile.

For example:

"My name is Saumya."
→ store name.

"I like Akarsh."
→ do not add this to CitizenProfile.

"Which person do I like?"
→ answer using conversation history when available.

==================================================
OUTPUT
==================================================

Return a structured ProfileAgentOutput containing:

profile
profile_complete
profile_valid
missing_information
validation_issues
response
"""


# ---------------------------------------------------------
# PROFILE AGENT
# ---------------------------------------------------------

profile_agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    tools=[],
    response_format=ProfileAgentOutput,
)


# ---------------------------------------------------------
# PROFILE RESPONSE FUNCTION
# ---------------------------------------------------------

def get_profile_agent_response(
    user_input: str,
    current_profile: dict
) -> dict:

    prompt = f"""
Current citizen profile:

{current_profile}

New citizen message:

{user_input}

Update the profile using ONLY information explicitly provided
in the new citizen message.

Rules:

1. Preserve previously known information.
2. Replace previous values only when the citizen explicitly
   corrects them.
3. Extract every explicit profile attribute.
4. Normalize values when the meaning is clear.
5. Do not invent information.
6. Detect contradictions.
7. Do not unnecessarily ask for every possible profile field.
8. Return structured ProfileAgentOutput.
"""

    response = profile_agent.invoke(
        {
            "messages": [
                HumanMessage(content=prompt)
            ]
        }
    )

    structured = response["structured_response"]

    return {
        "response": structured.response,

        "profile": structured.profile.model_dump(
            exclude_none=True
        ),

        # Keep LLM assessment available for debugging,
        # but graph.py will calculate the final value.
        "profile_complete": structured.profile_complete,

        "profile_valid": structured.profile_valid,

        "missing_information": structured.missing_information,

        "validation_issues": structured.validation_issues,
    }