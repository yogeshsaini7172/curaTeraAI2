import re
import sys
from pathlib import Path

def update_graph():
    graph_path = Path("c:/MY_PROJECTS/CuraTera/curaTeraAI2/agents/graph.py")
    with open(graph_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add import
    import_stmt = "from services.identity_verifier import (\n    verify_demo_identity\n)\n"
    if "from services.identity_verifier" not in content:
        content = content.replace("from agents.state import CuraTerraState", 
                                  "from agents.state import CuraTerraState\n" + import_stmt)
    
    # 2. Update profile_node complete return
    profile_node_return_old = """    return {
        "citizen_profile": new_profile,
        "profile_complete": profile_complete,
        "profile_changed": profile_changed,
        "profile_valid": result.get(
            "profile_valid",
            True
        ),
        "missing_information": missing_information,
        "validation_issues": result.get(
            "validation_issues",
            []
        ),
        "execution_mode": "profile_completion",
        "final_response": result.get(
            "response",
            ""
        ),
    }"""
    
    profile_node_return_new = """    return {
        "citizen_profile": new_profile,

        "profile_complete": profile_complete,

        "profile_changed": profile_changed,

        "profile_valid": result.get(
            "profile_valid",
            True
        ),

        "missing_information": [],

        "validation_issues": result.get(
            "validation_issues",
            []
        ),

        # --------------------------------------------------------
        # Identity verification
        # --------------------------------------------------------

        "identity_verified": state.get(
            "identity_verified",
            False
        ),

        "identity_verification_required": not state.get(
            "identity_verified",
            False
        ),

        "execution_mode": "profile_completion",

        "agent_outputs": {},

        "eligibility_results": None,
        "recommendations": None,
        "rag_response": "",
        "rag_citations": [],
        "application_response": "",
        "application_citations": [],

        "planned_tasks": [],

        "task_index": 0,
    }"""

    if profile_node_return_old in content:
        content = content.replace(profile_node_return_old, profile_node_return_new)
    
    # 3. Update route_after_profile
    route_after_profile_old = """def route_after_profile(
    state: CuraTerraState
) -> str:

    if not state.get(
        "profile_valid",
        True
    ):
        return "finalize"

    if state.get(
        "profile_complete",
        False
    ):
        return "eligibility"

    return "finalize"
"""
    route_after_profile_new = """def route_after_profile(
    state: CuraTerraState
) -> str:

    if not state.get(
        "profile_valid",
        True
    ):
        return "finalize"

    if not state.get(
        "profile_complete",
        False
    ):
        return "finalize"

    # Profile complete but identity not verified
    if not state.get(
        "identity_verified",
        False
    ):
        return "finalize"

    return "eligibility"
"""
    if route_after_profile_old in content:
        content = content.replace(route_after_profile_old, route_after_profile_new)

    # 4 & 5. Add identity verification node and route
    identity_nodes = """# ============================================================
# IDENTITY VERIFICATION NODE
# ============================================================

def identity_verification_node(
    state: CuraTerraState
):

    aadhaar_demo_id = state.get(
        "identity_verification_input"
    )

    profile = state.get(
        "citizen_profile",
        {}
    )

    if not aadhaar_demo_id:

        return {
            "identity_verified": False,

            "identity_verification_required": True,

            "identity_verification_result": {
                "verified": False,
                "reason": "No Aadhaar demo ID was provided."
            }
        }

    result = verify_demo_identity(
        aadhaar_demo_id=aadhaar_demo_id,
        profile=profile
    )

    if result.get("verified"):

        return {
            "identity_verified": True,

            "identity_verification_required": False,

            "identity_verification_result": result,

            # Clear the input after verification
            "identity_verification_input": None,

            "execution_mode": "profile_completion",

            "task_index": 0,
        }

    return {
        "identity_verified": False,

        "identity_verification_required": True,

        "identity_verification_result": result,

        "identity_verification_input": None,
    }

def route_after_identity_verification(
    state: CuraTerraState
) -> str:

    if state.get(
        "identity_verified",
        False
    ):
        return "eligibility"

    return "finalize"

"""
    if "def identity_verification_node(" not in content:
        # Insert before eligibility_node
        content = content.replace("# ============================================================\n# ELIGIBILITY NODE\n# ============================================================", identity_nodes + "# ============================================================\n# ELIGIBILITY NODE\n# ============================================================")

    # 6. route_from_start
    route_from_start_old = """def route_from_start(
    state: CuraTerraState
) -> str:

    if state.get(
        "profile_complete",
        False
    ):
        return "planner"

    return "profile"
"""
    route_from_start_new = """def route_from_start(
    state: CuraTerraState
) -> str:

    # A verification button submitted data
    if state.get(
        "identity_verification_input"
    ):
        return "identity_verification"

    if not state.get(
        "profile_complete",
        False
    ):
        return "profile"

    if not state.get(
        "identity_verified",
        False
    ):
        return "finalize"

    user_query = state.get("user_query", "").lower()
    if "profile" in user_query or "change" in user_query or "update" in user_query:
        return "profile"

    return "planner"
"""
    if route_from_start_old in content:
        content = content.replace(route_from_start_old, route_from_start_new)

    # 7. Add nodes and edges to build_graph
    if 'builder.add_node(\n        "identity_verification",' not in content:
        content = content.replace('builder.add_node(\n        "profile",\n        profile_node\n    )', 'builder.add_node(\n        "profile",\n        profile_node\n    )\n\n    builder.add_node(\n        "identity_verification",\n        identity_verification_node\n    )')
    
    start_edges_old = """    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "profile": "profile",
            "planner": "planner",
        }
    )"""
    start_edges_new = """    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "profile": "profile",
            "identity_verification": "identity_verification",
            "planner": "planner",
            "finalize": "finalize",
        }
    )"""
    if start_edges_old in content:
        content = content.replace(start_edges_old, start_edges_new)

    identity_edge = """    builder.add_conditional_edges(
        "identity_verification",
        route_after_identity_verification,
        {
            "eligibility": "eligibility",
            "finalize": "finalize",
        }
    )"""
    if "route_after_identity_verification" not in content.split("build_graph")[1]:
        content = content.replace('builder.add_conditional_edges(\n        "profile",\n        route_after_profile,\n        {\n            "eligibility": "eligibility",\n            "finalize": "finalize",\n        }\n    )', 'builder.add_conditional_edges(\n        "profile",\n        route_after_profile,\n        {\n            "eligibility": "eligibility",\n            "finalize": "finalize",\n        }\n    )\n\n' + identity_edge)

    # 8. finalize_node modifications
    finalize_start = """def finalize_node(
    state: CuraTerraState
):"""
    
    finalize_insert = """

    # ============================================================
    # IDENTITY VERIFICATION REQUIRED
    # ============================================================

    if (
        state.get("profile_complete", False)
        and not state.get("identity_verified", False)
        and not state.get("identity_verification_result")
    ):

        profile = state.get(
            "citizen_profile",
            {}
        )

        return {
            "final_response": {
                "message": (
                    "Before I can create your personalized "
                    "government-scheme profile, I need to "
                    "verify your identity. 🔐"
                ),

                "blocks": [
                    {
                        "type": "identity_verification",

                        "data": {
                            "required": True,

                            "name": profile.get(
                                "name"
                            ),

                            "age": profile.get(
                                "age"
                            ),

                            "gender": profile.get(
                                "gender"
                            ),

                            "state": profile.get(
                                "state"
                            ),

                            "district": profile.get(
                                "district"
                            )
                        }
                    }
                ],

                "citations": [],

                "profile": profile,

                "metadata": {
                    "intent": "identity_verification",

                    "requires_identity_verification": True
                }
            }
        }

    verification_result = state.get(
        "identity_verification_result"
    )

    if (
        verification_result
        and not verification_result.get(
            "verified",
            False
        )
    ):

        return {
            "final_response": {
                "message": (
                    "❌ Identity verification was not successful.\\n\\n"
                    "Some identity details did not match your "
                    "provided profile information. Please check "
                    "the details and try again."
                ),

                "blocks": [
                    {
                        "type": "identity_verification",

                        "data": {
                            "required": True,

                            "matched_fields":
                                verification_result.get(
                                    "matched_fields",
                                    []
                                ),

                            "failed_fields":
                                verification_result.get(
                                    "failed_fields",
                                    []
                                )
                        }
                    }
                ],

                "citations": [],

                "profile": state.get(
                    "citizen_profile",
                    {}
                ),

                "metadata": {
                    "intent": "identity_verification",

                    "verification_failed": True
                }
            }
        }
"""
    if "IDENTITY VERIFICATION REQUIRED" not in content:
        content = content.replace(finalize_start, finalize_start + finalize_insert)

    with open(graph_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Success")

if __name__ == "__main__":
    update_graph()
