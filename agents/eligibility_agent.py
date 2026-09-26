from langchain.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from ml.eligibility.rule_parser import load_rules
from ml.eligibility.engine import evaluate_all_schemes


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# LOAD ALL ELIGIBILITY RULES
# ============================================================

RULES_PATH = "data/processed/eligibility_rules.csv"

rules = load_rules(RULES_PATH)


# ============================================================
# LLM
# ============================================================

model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


# ============================================================
# ELIGIBILITY AGENT
# ============================================================

def get_eligibility_agent_response(profile: dict) -> str:
    """
    Evaluate a citizen against all scheme rules.

    The deterministic eligibility engine is the only source
    of truth. The LLM is used only to present the results.
    """

    # --------------------------------------------------------
    # STEP 1: RUN DETERMINISTIC ELIGIBILITY ENGINE
    # --------------------------------------------------------

    results = evaluate_all_schemes(
        profile,
        rules
    )

    # --------------------------------------------------------
    # STEP 2: DEBUG OUTPUT
    # --------------------------------------------------------

    print("\n[ELIGIBILITY ENGINE DEBUG]")

    # Print S039 specifically for debugging
    s039_result = next(
        (
            result
            for result in results
            if str(result.get("scheme_id", "")).strip().upper() == "S039"
        ),
        None
    )

    if s039_result is not None:

        print("\nS039 complete result:")
        print(s039_result)

        print("\nS039 failed rules:")
        print(s039_result.get("failed_rules", []))

        print("\nS039 missing information:")
        print(s039_result.get("missing_information", []))

        print("\nS039 passed rules:")
        print(s039_result.get("passed_rules", []))

    else:
        print("\nS039 was not found in the loaded rules.")

    # --------------------------------------------------------
    # STEP 3: BUILD PRESENTATION SUMMARY
    # --------------------------------------------------------

    eligible_schemes = []
    missing_information_schemes = []

    for result in results:

        scheme_id = result.get("scheme_id")
        status = result.get("status")

        # --------------------------------------------
        # ELIGIBLE
        # --------------------------------------------

        if status == "eligible":

            eligible_schemes.append({
                "scheme_id": scheme_id,
                "passed_rules": result.get(
                    "passed_rules",
                    []
                )
            })

        # --------------------------------------------
        # MISSING INFORMATION
        # --------------------------------------------

        elif status == "missing_information":

            missing_information_schemes.append({
                "scheme_id": scheme_id,
                "missing": result.get(
                    "missing_information",
                    []
                )
            })

        # --------------------------------------------
        # NOT ELIGIBLE
        #
        # Intentionally not added to the user summary.
        # The engine still evaluates these schemes.
        # --------------------------------------------

    summary = {
        "eligible": eligible_schemes,
        "missing_information": missing_information_schemes
    }

    # --------------------------------------------------------
    # STEP 4: NO ELIGIBLE / NO MISSING INFORMATION
    # --------------------------------------------------------

    if not eligible_schemes and not missing_information_schemes:

        return (
            "Based on the information provided, "
            "you are not currently eligible for any "
            "of the available schemes."
        )

    # --------------------------------------------------------
    # STEP 5: LLM PRESENTATION
    # --------------------------------------------------------

    prompt = f"""
You are CuraTera's Eligibility Agent.

Your role is ONLY to present the eligibility results
produced by the deterministic eligibility engine.

Eligibility engine results:

{summary}

Strict rules:

1. The eligibility engine is the only source of truth.
2. Do not calculate eligibility yourself.
3. Do not infer eligibility yourself.
4. Do not change any eligibility decision.
5. Do not invent scheme facts.
6. Mention only schemes explicitly present in the results.
7. For eligible schemes, mention the verified matching
   information contained in passed_rules.
8. For missing information, mention only the missing fields
   provided by the engine.
9. Never treat missing information as not eligible.
10. Do not explain rejected schemes.
11. Do not provide benefits.
12. Do not provide documents.
13. Do not provide application procedures.
14. Do not provide application links.
15. Do not recommend or rank schemes.
16. Do not tell the citizen to apply.
17. Do not mention internal agents, Python, engines,
    tools, rules files, or implementation details.
18. Answer in the citizen's language.
19. Keep the response concise and clear.

Present the result naturally to the citizen.
"""

    response = model.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )

    return response.content


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    profile = {
        "name": "Akarsh Tiwari",
        "age": 24,
        "gender": "male",
        "state": "Uttar Pradesh",
        "district": "Lucknow",
        "rural_or_urban": "urban",
        "social_category": "general",
        "annual_family_income": 300000,
        "occupation": "Associate at Accenture",
        "farmer_status": True,
        "education_level": "B.Tech",
        "student_status": True
    }

    response = get_eligibility_agent_response(
        profile
    )

    print("\n=== ELIGIBILITY AGENT RESPONSE ===")
    print(response)
