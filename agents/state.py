from typing import TypedDict, Any, Annotated
import operator

class CuraTerraState(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]
    user_query: str

    # Profile
    citizen_profile: dict
    profile_complete: bool
    profile_changed: bool

    profile_valid: bool
    missing_information: list[str]
    validation_issues: list[str]

    # Execution
    execution_mode: str

    # Planner / Router
    router_intent: str
    planned_tasks: list[str]
    task_index: int
    scheme_reference: str | None

    # Current scheme context
    current_scheme_id: str | None
    current_scheme_name: str | None

    # Agent results
    eligibility_results: Any
    recommendations: Any

    rag_response: str
    rag_citations: list

    application_response: str
    application_citations: list

    # Raw outputs from agents
    agent_outputs: dict

    # Final answer
    final_response: str