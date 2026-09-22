# import json
# import re

# from langchain.messages import HumanMessage
# from langchain.agents import create_agent
# from langchain_groq import ChatGroq
# from langgraph.graph import StateGraph, START, END

# from agents.state import CuraTerraState
# from schemas import QueryPlan
# from memory.checkpointer import checkpointer

# from agents.profile_agent import get_profile_agent_response
# from agents.eligibility_agent import get_eligibility_agent_response
# from agents.recommendation_agent import get_recommendation_response
# from agents.rag_agent import get_rag_response
# from agents.application_agent import get_application_response


# # ============================================================
# # MODEL
# # ============================================================

# planner_model = ChatGroq(
#     model="openai/gpt-oss-120b",
#     temperature=0
# )


# # ============================================================
# # QUERY PLANNER
# # ============================================================

# planner_system_prompt = """
# You are CuraTera's Context-Aware Query Planner.

# Your ONLY job is to understand the citizen's CURRENT message
# and create the smallest correct execution plan.

# You are a ROUTER, not the final answer generator.

# Use:
# - current citizen profile
# - current scheme
# - previous conversation/agent outputs
# - current user message

# AVAILABLE TASKS:

# 1. eligibility
# Use when the user asks:
# - Am I eligible?
# - Do I qualify?
# - Which schemes can I get?
# - Can I get this scheme?
# - Check my eligibility.

# 2. recommendation
# Use when the user asks:
# - Which scheme is best?
# - Which scheme is suitable?
# - What do you recommend?
# - Which one should I choose?

# 3. rag
# Use for verified scheme information:
# - benefits
# - scheme details
# - scheme rules
# - scheme explanation
# - amount/funding
# - coverage
# - FAQs

# 4. application
# Use for:
# - how to apply
# - where to apply
# - application process
# - portal
# - registration
# - required documents
# - application steps

# 5. general
# Use for:
# - greetings
# - thanks
# - acknowledgements
# - casual conversation
# - general knowledge
# - programming
# - coding
# - unrelated questions
# - simple clarification
# - normal conversation

# 6. clarification
# Use when the user asks about a scheme-specific subject
# but there is NO explicit scheme and NO current scheme context.

# Examples:
# "What are the benefits of this scheme?"
# "How do I apply for it?"
# "What documents are needed?"
# when no scheme has been established.

# IMPORTANT CONTEXT RULES:

# If the user explicitly mentions a scheme, extract it.

# Examples:
# "S039"       -> scheme_reference = S039
# "scheme 20"  -> scheme_reference = S020
# "S01"        -> scheme_reference = S001
# "S1"         -> scheme_reference = S001

# If the user says:
# - this scheme
# - that scheme
# - it
# - this
# - that one
# - tell me more

# and a current scheme exists, use that current scheme.

# Examples:

# Current scheme = S039
# User: "tell me more"
# -> ["rag"]

# Current scheme = S039
# User: "how do I apply?"
# -> ["application"]

# Current scheme = S039
# User: "what documents do I need?"
# -> ["application"]

# Current scheme = S039
# User: "okay thank you"
# -> ["general"]

# If there is NO current scheme and the user says:
# "how do I apply for this?"
# -> ["clarification"]

# If there is NO current scheme and the user says:
# "what are the benefits of this scheme?"
# -> ["clarification"]

# NEVER guess a scheme.

# NEVER send an unknown scheme-specific question
# to RAG across all schemes.

# NEVER add eligibility or recommendation merely because
# an application query has no scheme.

# Multiple tasks are allowed.

# Never return "profile" as a task.
# Never answer the user yourself.
# """


# planner_agent = create_agent(
#     model=planner_model,
#     system_prompt=planner_system_prompt,
#     tools=[],
#     response_format=QueryPlan,
# )


# # ============================================================
# # PROFILE COMPLETENESS
# # ============================================================

# CORE_PROFILE_FIELDS = [
#     "age",
#     "state",
#     "district",
#     "gender",
#     "social_category",
#     "annual_family_income",
#     "occupation",
# ]


# def check_profile_completeness(profile: dict):

#     missing = []

#     for field in CORE_PROFILE_FIELDS:

#         value = profile.get(field)

#         if value is None:
#             missing.append(field)

#         elif isinstance(value, str) and not value.strip():
#             missing.append(field)

#     return len(missing) == 0, missing


# # ============================================================
# # SCHEME ID NORMALIZATION
# # ============================================================

# def normalize_scheme_id(scheme_id):

#     if scheme_id is None:
#         return None

#     scheme_id = str(scheme_id).strip().upper()

#     if not scheme_id:
#         return None

#     # 20 -> S020
#     if scheme_id.isdigit():
#         return f"S{int(scheme_id):03d}"

#     # S20 -> S020
#     if scheme_id.startswith("S"):

#         number = scheme_id[1:]

#         if number.isdigit():
#             return f"S{int(number):03d}"

#     return scheme_id


# # ============================================================
# # PROFILE NODE
# # ============================================================

# def profile_node(state: CuraTerraState):

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     current_profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     result = get_profile_agent_response(
#         user_input=user_query,
#         current_profile=current_profile
#     )

#     old_profile = current_profile

#     new_profile = result.get(
#         "profile",
#         {}
#     )

#     profile_changed = (
#         old_profile != new_profile
#     )

#     profile_complete, missing_information = (
#         check_profile_completeness(
#             new_profile
#         )
#     )

#     print("\n[PROFILE DEBUG]")
#     print("Extracted profile:", new_profile)
#     print(
#         "LLM profile_complete:",
#         result.get("profile_complete")
#     )
#     print(
#         "Python profile_complete:",
#         profile_complete
#     )
#     print(
#         "Missing fields:",
#         missing_information
#     )

#     return {
#         "citizen_profile": new_profile,
#         "profile_complete": profile_complete,
#         "profile_changed": profile_changed,
#         "profile_valid": result.get(
#             "profile_valid",
#             True
#         ),
#         "missing_information": missing_information,
#         "validation_issues": result.get(
#             "validation_issues",
#             []
#         ),
#         "execution_mode": "profile_completion",
#         "final_response": result.get(
#             "response",
#             ""
#         ),
#     }


# # ============================================================
# # ELIGIBILITY NODE
# # ============================================================

# def eligibility_node(state: CuraTerraState):

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     result = get_eligibility_agent_response(
#         profile
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["eligibility"] = {
#         "answer": result,
#         "citations": []
#     }

#     return {
#         "eligibility_results": result,
#         "agent_outputs": outputs,
#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),
#     }


# # ============================================================
# # RECOMMENDATION NODE
# # ============================================================

# def recommendation_node(state: CuraTerraState):

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     eligibility_results = state.get(
#         "eligibility_results"
#     )

#     recommendation_input = {
#         "citizen_profile": profile,
#         "eligibility_results": eligibility_results
#     }

#     result = get_recommendation_response(
#         str(recommendation_input)
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["recommendation"] = result

#     top_scheme_id = None

#     if isinstance(result, dict):

#         top_scheme_id = result.get(
#             "top_scheme_id"
#         )

#         answer = result.get(
#             "answer",
#             str(result)
#         )

#     else:

#         answer = str(result)

#         match = re.search(
#             r"\bS\d{1,3}\b",
#             answer.upper()
#         )

#         if match:
#             top_scheme_id = match.group(0)

#     top_scheme_id = normalize_scheme_id(
#         top_scheme_id
#     )

#     return {
#         "recommendations": result,

#         "current_scheme_id": (
#             top_scheme_id
#             or state.get(
#                 "current_scheme_id"
#             )
#         ),

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),

#         "final_response": answer,
#     }


# # ============================================================
# # RAG NODE
# # ============================================================

# def rag_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     print("\n[RAG]")
#     print("Query:", query)
#     print("Scheme ID:", scheme_id)

#     result = get_rag_response(
#         query=query,
#         retrieval_k=10,
#         final_k=5,
#         scheme_id=scheme_id
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["rag"] = {
#         "answer": result["answer"],
#         "citations": result["citations"]
#     }

#     return {
#         "rag_response": result["answer"],
#         "rag_citations": result["citations"],
#         "agent_outputs": outputs,
#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # APPLICATION NODE
# # ============================================================

# def application_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     print("\n[APPLICATION]")
#     print("Query:", query)
#     print("Scheme ID:", scheme_id)

#     result = get_application_response(
#         query=query,
#         retrieval_k=10,
#         final_k=5,
#         scheme_id=scheme_id
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["application"] = {
#         "answer": result["answer"],
#         "citations": result["citations"]
#     }

#     return {
#         "application_response": result["answer"],
#         "application_citations": result["citations"],
#         "agent_outputs": outputs,
#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # GENERAL CONVERSATION NODE
# # ============================================================

# def general_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     current_scheme = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     previous_outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     prompt = f"""
# You are CuraTera AI's general conversational assistant.

# Citizen profile:

# {json.dumps(
#     profile,
#     ensure_ascii=False,
#     default=str
# )}

# Current scheme:

# {current_scheme}

# Previous agent result:

# {json.dumps(
#     previous_outputs,
#     ensure_ascii=False,
#     default=str
# )}

# Current user message:

# {query}

# Respond naturally.

# Rules:

# 1. Handle greetings naturally.
# 2. Handle thanks and acknowledgements naturally.
# 3. Handle casual conversation naturally.
# 4. Answer general knowledge questions.
# 5. Answer programming and coding questions.
# 6. Do not make eligibility decisions.
# 7. Do not invent government scheme facts.
# 8. Do not invent benefits, documents, or application steps.
# 9. Do not mention internal agents, planners, tools,
#    or implementation details.
# 10. Match the user's language.
# 11. Keep the response concise and useful.
# """

#     response = planner_model.invoke(
#         [
#             HumanMessage(
#                 content=prompt
#             )
#         ]
#     )

#     answer = response.content

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["general"] = {
#         "answer": answer,
#         "citations": []
#     }

#     return {
#         "general_response": answer,
#         "agent_outputs": outputs,
#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),
#         "final_response": answer,
#     }


# # ============================================================
# # CLARIFICATION NODE
# # ============================================================

# def clarification_node(state: CuraTerraState):

#     current_scheme = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     if current_scheme:

#         message = (
#             f"Are you referring to scheme {current_scheme}?"
#         )

#     else:

#         message = (
#             "Which government scheme are you referring to? "
#             "Please provide the scheme ID, such as S020 or S039."
#         )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["clarification"] = {
#         "answer": message,
#         "citations": []
#     }

#     return {
#         "clarification_response": message,
#         "agent_outputs": outputs,
#         "final_response": message,
#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # FALLBACK ROUTER
# # ============================================================

# def fallback_route_query(
#     state: CuraTerraState
# ) -> str:

#     query = (
#         state.get(
#             "user_query",
#             ""
#         )
#         .strip()
#         .lower()
#     )

#     eligibility_keywords = [
#         "eligible",
#         "eligibility",
#         "qualify",
#         "qualification",
#         "am i eligible",
#         "do i qualify",
#         "can i get"
#     ]

#     application_keywords = [
#         "how to apply",
#         "how do i apply",
#         "where to apply",
#         "application process",
#         "application form",
#         "application portal",
#         "portal",
#         "registration",
#         "register",
#         "documents required",
#         "what documents",
#         "document"
#     ]

#     recommendation_keywords = [
#         "recommend",
#         "recommendation",
#         "which scheme",
#         "best scheme",
#         "suitable scheme",
#         "which one",
#         "most relevant",
#         "what should i choose"
#     ]

#     rag_keywords = [
#         "benefit",
#         "benefits",
#         "details",
#         "scheme details",
#         "tell me about",
#         "what is this scheme",
#         "scheme information",
#         "how much",
#         "amount",
#         "funding",
#         "rules",
#         "faq"
#     ]

#     if any(
#         keyword in query
#         for keyword in eligibility_keywords
#     ):
#         return "eligibility"

#     if any(
#         keyword in query
#         for keyword in application_keywords
#     ):
#         return "application"

#     if any(
#         keyword in query
#         for keyword in recommendation_keywords
#     ):
#         return "recommendation"

#     if any(
#         keyword in query
#         for keyword in rag_keywords
#     ):
#         return "rag"

#     return "general"


# # ============================================================
# # ALLOWED TASKS
# # ============================================================

# ALLOWED_TASKS = {
#     "eligibility",
#     "recommendation",
#     "rag",
#     "application",
#     "general",
#     "clarification",
# }


# # ============================================================
# # PLAN DEPENDENCY RESOLVER
# # ============================================================

# def resolve_plan(
#     tasks: list[str],
#     state: CuraTerraState,
#     scheme_reference: str | None
# ) -> list[str]:

#     cleaned = []

#     for task in tasks:

#         task = (
#             str(task)
#             .strip()
#             .lower()
#         )

#         if (
#             task in ALLOWED_TASKS
#             and task not in cleaned
#         ):
#             cleaned.append(task)

#     # --------------------------------------------------------
#     # Nothing recognized
#     # --------------------------------------------------------

#     if not cleaned:
#         return ["general"]

#     # --------------------------------------------------------
#     # Current scheme
#     # --------------------------------------------------------

#     current_scheme = normalize_scheme_id(
#         scheme_reference
#         or state.get(
#             "current_scheme_id"
#         )
#     )

#     # --------------------------------------------------------
#     # RAG / Application need a scheme
#     #
#     # Do NOT guess.
#     # Do NOT add eligibility/recommendation.
#     # --------------------------------------------------------

#     if (
#         (
#             "rag" in cleaned
#             or "application" in cleaned
#         )
#         and not current_scheme
#     ):
#         return ["clarification"]

#     # --------------------------------------------------------
#     # Recommendation needs eligibility
#     # --------------------------------------------------------

#     has_eligibility = bool(
#         state.get(
#             "eligibility_results"
#         )
#     )

#     if (
#         "recommendation" in cleaned
#         and not has_eligibility
#         and "eligibility" not in cleaned
#     ):
#         cleaned.append(
#             "eligibility"
#         )

#     # --------------------------------------------------------
#     # Execution priority
#     # --------------------------------------------------------

#     priority = {
#         "eligibility": 0,
#         "recommendation": 1,
#         "rag": 2,
#         "application": 3,
#         "general": 4,
#         "clarification": 5,
#     }

#     cleaned.sort(
#         key=lambda task: priority[task]
#     )

#     return cleaned


# # ============================================================
# # PLANNER NODE
# # ============================================================

# def planner_node(state: CuraTerraState):

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     current_scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#     )

#     previous_outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     eligibility_exists = bool(
#         state.get(
#             "eligibility_results"
#         )
#     )

#     recommendation_exists = bool(
#         state.get(
#             "recommendations"
#         )
#     )

#     prompt = f"""
# Current citizen profile:

# {json.dumps(
#     profile,
#     indent=2,
#     ensure_ascii=False,
#     default=str
# )}

# Current scheme:

# {current_scheme_id}

# Previous agent outputs:

# {json.dumps(
#     previous_outputs,
#     indent=2,
#     ensure_ascii=False,
#     default=str
# )}

# Previous eligibility result exists:
# {eligibility_exists}

# Previous recommendation exists:
# {recommendation_exists}

# Current user message:

# {user_query}

# Create the smallest correct execution plan.

# Important:

# - Understand the user's current message using context.
# - If the user says "this scheme", "that scheme", "it",
#   "tell me more", "which one", etc., use current scheme
#   context when available.
# - If no scheme exists and the user asks for scheme-specific
#   benefits, documents, details, or application information,
#   use clarification.
# - Never guess a scheme.
# - Do not add eligibility or recommendation just because
#   application has no scheme.
# - Use general for greetings, thanks, acknowledgements,
#   casual conversation, coding, programming, or unrelated
#   questions.
# - Multiple tasks are allowed.
# - Do not answer the user.
# - Do not return profile.
# """

#     try:

#         response = planner_agent.invoke(
#             {
#                 "messages": [
#                     HumanMessage(
#                         content=prompt
#                     )
#                 ]
#             }
#         )

#         structured = response[
#             "structured_response"
#         ]

#         raw_tasks = list(
#             structured.tasks
#         )

#         scheme_reference = normalize_scheme_id(
#             structured.scheme_reference
#             or current_scheme_id
#         )

#         primary_task = (
#             structured.primary_task
#             or (
#                 raw_tasks[0]
#                 if raw_tasks
#                 else "general"
#             )
#         )

#     except Exception as error:

#         print(
#             "\n[PLANNER WARNING]",
#             error
#         )

#         fallback_task = fallback_route_query(
#             state
#         )

#         raw_tasks = [
#             fallback_task
#         ]

#         scheme_reference = (
#             current_scheme_id
#         )

#         primary_task = fallback_task

#     planned_tasks = resolve_plan(
#         raw_tasks,
#         state,
#         scheme_reference
#     )

#     print("\n[PLANNER]")
#     print(
#         "User query:",
#         user_query
#     )
#     print(
#         "Raw tasks:",
#         raw_tasks
#     )
#     print(
#         "Resolved tasks:",
#         planned_tasks
#     )
#     print(
#         "Scheme reference:",
#         scheme_reference
#     )

#     return {
#         "planned_tasks": planned_tasks,
#         "task_index": 0,
#         "router_intent": primary_task,
#         "scheme_reference": scheme_reference,
#         "current_scheme_id": scheme_reference,
#         "execution_mode": "normal_query",
#         "agent_outputs": {},
#         "profile_changed": False,
#     }


# # ============================================================
# # START ROUTING
# # ============================================================

# def route_from_start(
#     state: CuraTerraState
# ) -> str:

#     if state.get(
#         "profile_complete",
#         False
#     ):
#         return "planner"

#     return "profile"


# # ============================================================
# # AFTER PROFILE
# # ============================================================

# def route_after_profile(
#     state: CuraTerraState
# ) -> str:

#     if not state.get(
#         "profile_valid",
#         True
#     ):
#         return "end"

#     if state.get(
#         "profile_complete",
#         False
#     ):
#         return "eligibility"

#     return "end"


# # ============================================================
# # NEXT TASK
# # ============================================================

# def route_next_task(
#     state: CuraTerraState
# ) -> str:

#     tasks = state.get(
#         "planned_tasks",
#         []
#     )

#     index = state.get(
#         "task_index",
#         0
#     )

#     if index >= len(tasks):
#         return "finalize"

#     return tasks[index]


# # ============================================================
# # AFTER ELIGIBILITY
# # ============================================================

# def route_after_eligibility(
#     state: CuraTerraState
# ) -> str:

#     if (
#         state.get(
#             "execution_mode"
#         )
#         == "profile_completion"
#     ):
#         return "recommendation"

#     return route_next_task(
#         state
#     )


# # ============================================================
# # AFTER RECOMMENDATION
# # ============================================================

# def route_after_recommendation(
#     state: CuraTerraState
# ) -> str:

#     if (
#         state.get(
#             "execution_mode"
#         )
#         == "profile_completion"
#     ):
#         return "finalize"

#     return route_next_task(
#         state
#     )


# # ============================================================
# # FINALIZE
# # ============================================================

# def finalize_node(
#     state: CuraTerraState
# ):

#     outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     # --------------------------------------------------------
#     # Nothing returned
#     # --------------------------------------------------------

#     if not outputs:

#         return {
#             "final_response": (
#                 state.get(
#                     "final_response"
#                 )
#                 or (
#                     "I couldn't determine the right "
#                     "information for your request."
#                 )
#             )
#         }

#     # --------------------------------------------------------
#     # General / clarification
#     #
#     # Already final. No extra LLM call.
#     # --------------------------------------------------------

#     if (
#         "general" in outputs
#         or "clarification" in outputs
#     ):

#         key = (
#             "general"
#             if "general" in outputs
#             else "clarification"
#         )

#         value = outputs[key]

#         if isinstance(
#             value,
#             dict
#         ):

#             answer = value.get(
#                 "answer"
#             )

#             if answer:
#                 return {
#                     "final_response": answer
#                 }

#         return {
#             "final_response": str(
#                 value
#             )
#         }

#     # --------------------------------------------------------
#     # Single specialist agent
#     # --------------------------------------------------------

#     if len(outputs) == 1:

#         value = next(
#             iter(
#                 outputs.values()
#             )
#         )

#         if isinstance(
#             value,
#             dict
#         ):

#             answer = value.get(
#                 "answer"
#             )

#             if answer:
#                 return {
#                     "final_response": answer
#                 }

#         return {
#             "final_response": str(
#                 value
#             )
#         }

#     # --------------------------------------------------------
#     # Multiple specialist agents
#     # --------------------------------------------------------

#     prompt = f"""
# You are CuraTera's final response synthesizer.

# Citizen query:

# {user_query}

# Agent outputs:

# {json.dumps(
#     outputs,
#     indent=2,
#     ensure_ascii=False,
#     default=str
# )}

# Rules:

# 1. Eligibility results are authoritative.
# 2. Never change an eligibility decision.
# 3. Never invent benefits, documents, or application steps.
# 4. Use RAG/application information only as evidence.
# 5. Use recommendation only for ranking/relevance.
# 6. Preserve citations when available.
# 7. Answer in the citizen's language.
# 8. Do not mention agents, planners, tools, or internal state.
# 9. Combine the requested tasks naturally.
# 10. Keep the answer concise but complete.
# """

#     response = planner_model.invoke(
#         [
#             HumanMessage(
#                 content=prompt
#             )
#         ]
#     )

#     return {
#         "final_response": response.content
#     }


# # ============================================================
# # BUILD GRAPH
# # ============================================================

# def build_graph():

#     builder = StateGraph(
#         CuraTerraState
#     )

#     # --------------------------------------------------------
#     # Nodes
#     # --------------------------------------------------------

#     builder.add_node(
#         "profile",
#         profile_node
#     )

#     builder.add_node(
#         "planner",
#         planner_node
#     )

#     builder.add_node(
#         "eligibility",
#         eligibility_node
#     )

#     builder.add_node(
#         "recommendation",
#         recommendation_node
#     )

#     builder.add_node(
#         "rag",
#         rag_node
#     )

#     builder.add_node(
#         "application",
#         application_node
#     )

#     builder.add_node(
#         "general",
#         general_node
#     )

#     builder.add_node(
#         "clarification",
#         clarification_node
#     )

#     builder.add_node(
#         "finalize",
#         finalize_node
#     )

#     # --------------------------------------------------------
#     # START
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         START,
#         route_from_start,
#         {
#             "profile": "profile",
#             "planner": "planner",
#         }
#     )

#     # --------------------------------------------------------
#     # PROFILE
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "profile",
#         route_after_profile,
#         {
#             "eligibility": "eligibility",
#             "end": END,
#         }
#     )

#     # --------------------------------------------------------
#     # PLANNER
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "planner",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # ELIGIBILITY
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "eligibility",
#         route_after_eligibility,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # RECOMMENDATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "recommendation",
#         route_after_recommendation,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # RAG
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "rag",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # APPLICATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "application",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # GENERAL
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "general",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # CLARIFICATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "clarification",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # FINALIZE
#     # --------------------------------------------------------

#     builder.add_edge(
#         "finalize",
#         END
#     )

#     # --------------------------------------------------------
#     # CHECKPOINTER
#     # --------------------------------------------------------

#     return builder.compile(
#         checkpointer=checkpointer
#     )











# ## 2

# import json
# import re

# from langchain.messages import HumanMessage
# from langchain.agents import create_agent
# from langchain_groq import ChatGroq
# from langgraph.graph import StateGraph, START, END

# from agents.state import CuraTerraState
# from schemas import QueryPlan
# from memory.checkpointer import checkpointer

# from agents.profile_agent import get_profile_agent_response
# from agents.eligibility_agent import get_eligibility_agent_response
# from agents.recommendation_agent import get_recommendation_response
# from agents.rag_agent import get_rag_response
# from agents.application_agent import get_application_response
# from agents.response_agent import generate_response


# # ============================================================
# # MODEL
# # ============================================================

# planner_model = ChatGroq(
#     model="openai/gpt-oss-120b",
#     temperature=0
# )


# # ============================================================
# # QUERY PLANNER
# # ============================================================

# planner_system_prompt = """
# You are CuraTera's Context-Aware Query Planner.

# Your ONLY job is to understand the citizen's CURRENT message
# and create the smallest correct execution plan.

# You are a ROUTER, not the final answer generator.

# Use:
# - current citizen profile
# - current scheme
# - previous conversation/agent outputs
# - current user message

# AVAILABLE TASKS:

# 1. eligibility
# Use when the user asks:
# - Am I eligible?
# - Do I qualify?
# - Which schemes can I get?
# - Can I get this scheme?
# - Check my eligibility.

# 2. recommendation
# Use when the user asks:
# - Which scheme is best?
# - Which scheme is suitable?
# - What do you recommend?
# - Which one should I choose?

# 3. rag
# Use for verified scheme information:
# - benefits
# - scheme details
# - scheme rules
# - scheme explanation
# - amount/funding
# - coverage
# - FAQs

# 4. application
# Use for:
# - how to apply
# - where to apply
# - application process
# - portal
# - registration
# - required documents
# - application steps

# 5. general
# Use for:
# - greetings
# - thanks
# - acknowledgements
# - casual conversation
# - general knowledge
# - programming
# - coding
# - unrelated questions
# - simple clarification
# - normal conversation

# 6. clarification
# Use when the user asks about a scheme-specific subject
# but there is NO explicit scheme and NO current scheme context.

# Examples:
# "What are the benefits of this scheme?"
# "How do I apply for it?"
# "What documents are needed?"
# when no scheme has been established.

# IMPORTANT CONTEXT RULES:

# If the user explicitly mentions a scheme, extract it.

# Examples:
# "S039"       -> scheme_reference = S039
# "scheme 20"  -> scheme_reference = S020
# "S01"        -> scheme_reference = S001
# "S1"         -> scheme_reference = S001

# If the user says:
# - this scheme
# - that scheme
# - it
# - this
# - that one
# - tell me more

# and a current scheme exists, use that current scheme.

# Examples:

# Current scheme = S039
# User: "tell me more"
# -> ["rag"]

# Current scheme = S039
# User: "how do I apply?"
# -> ["application"]

# Current scheme = S039
# User: "what documents do I need?"
# -> ["application"]

# Current scheme = S039
# User: "okay thank you"
# -> ["general"]

# If there is NO current scheme and the user says:
# "how do I apply for this?"
# -> ["clarification"]

# If there is NO current scheme and the user says:
# "what are the benefits of this scheme?"
# -> ["clarification"]

# NEVER guess a scheme.

# NEVER send an unknown scheme-specific question
# to RAG across all schemes.

# NEVER add eligibility or recommendation merely because
# an application query has no scheme.

# Multiple tasks are allowed.

# Never return "profile" as a task.
# Never answer the user yourself.
# """


# planner_agent = create_agent(
#     model=planner_model,
#     system_prompt=planner_system_prompt,
#     tools=[],
#     response_format=QueryPlan,
# )


# # ============================================================
# # PROFILE COMPLETENESS
# # ============================================================

# CORE_PROFILE_FIELDS = [
#     "age",
#     "state",
#     "district",
#     "gender",
#     "social_category",
#     "annual_family_income",
#     "occupation",
# ]


# def check_profile_completeness(profile: dict):

#     missing = []

#     for field in CORE_PROFILE_FIELDS:

#         value = profile.get(field)

#         if value is None:
#             missing.append(field)

#         elif isinstance(value, str) and not value.strip():
#             missing.append(field)

#     return len(missing) == 0, missing


# # ============================================================
# # SCHEME ID NORMALIZATION
# # ============================================================

# def normalize_scheme_id(scheme_id):

#     if scheme_id is None:
#         return None

#     scheme_id = str(scheme_id).strip().upper()

#     if not scheme_id:
#         return None

#     # 20 -> S020
#     if scheme_id.isdigit():
#         return f"S{int(scheme_id):03d}"

#     # S20 -> S020
#     if scheme_id.startswith("S"):

#         number = scheme_id[1:]

#         if number.isdigit():
#             return f"S{int(number):03d}"

#     return scheme_id


# # ============================================================
# # PROFILE NODE
# # ============================================================

# def profile_node(state: CuraTerraState):

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     current_profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     result = get_profile_agent_response(
#         user_input=user_query,
#         current_profile=current_profile
#     )

#     old_profile = current_profile

#     new_profile = result.get(
#         "profile",
#         {}
#     )

#     profile_changed = (
#         old_profile != new_profile
#     )

#     profile_complete, missing_information = (
#         check_profile_completeness(
#             new_profile
#         )
#     )

#     print("\n[PROFILE DEBUG]")
#     print(
#         "Extracted profile:",
#         new_profile
#     )

#     print(
#         "LLM profile_complete:",
#         result.get(
#             "profile_complete"
#         )
#     )

#     print(
#         "Python profile_complete:",
#         profile_complete
#     )

#     print(
#         "Missing fields:",
#         missing_information
#     )

#     return {
#         "citizen_profile": new_profile,

#         "profile_complete": profile_complete,

#         "profile_changed": profile_changed,

#         "profile_valid": result.get(
#             "profile_valid",
#             True
#         ),

#         "missing_information": (
#             missing_information
#         ),

#         "validation_issues": result.get(
#             "validation_issues",
#             []
#         ),

#         "execution_mode": (
#             "profile_completion"
#         ),

#         "final_response": result.get(
#             "response",
#             ""
#         ),
#     }


# # ============================================================
# # ELIGIBILITY NODE
# # ============================================================

# def eligibility_node(state: CuraTerraState):

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     result = get_eligibility_agent_response(
#         profile
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["eligibility"] = {
#         "answer": result,
#         "citations": []
#     }

#     return {
#         "eligibility_results": result,

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),
#     }


# # ============================================================
# # RECOMMENDATION NODE
# # ============================================================

# def recommendation_node(state: CuraTerraState):

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     eligibility_results = state.get(
#         "eligibility_results"
#     )

#     recommendation_input = {
#         "citizen_profile": profile,
#         "eligibility_results": eligibility_results
#     }

#     result = get_recommendation_response(
#         str(recommendation_input)
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["recommendation"] = result

#     top_scheme_id = None

#     if isinstance(result, dict):

#         top_scheme_id = result.get(
#             "top_scheme_id"
#         )

#         answer = result.get(
#             "answer",
#             str(result)
#         )

#     else:

#         answer = str(result)

#         match = re.search(
#             r"\bS\d{1,3}\b",
#             answer.upper()
#         )

#         if match:
#             top_scheme_id = match.group(0)

#     top_scheme_id = normalize_scheme_id(
#         top_scheme_id
#     )

#     return {
#         "recommendations": result,

#         "current_scheme_id": (
#             top_scheme_id
#             or state.get(
#                 "current_scheme_id"
#             )
#         ),

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),

#         "final_response": answer,
#     }


# # ============================================================
# # RAG NODE
# # ============================================================

# def rag_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     print("\n[RAG]")
#     print(
#         "Query:",
#         query
#     )

#     print(
#         "Scheme ID:",
#         scheme_id
#     )

#     result = get_rag_response(
#         query=query,
#         retrieval_k=10,
#         final_k=5,
#         scheme_id=scheme_id
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["rag"] = {
#         "answer": result["answer"],
#         "citations": result["citations"]
#     }

#     return {
#         "rag_response": result["answer"],

#         "rag_citations": result["citations"],

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # APPLICATION NODE
# # ============================================================

# def application_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     print("\n[APPLICATION]")
#     print(
#         "Query:",
#         query
#     )

#     print(
#         "Scheme ID:",
#         scheme_id
#     )

#     result = get_application_response(
#         query=query,
#         retrieval_k=10,
#         final_k=5,
#         scheme_id=scheme_id
#     )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["application"] = {
#         "answer": result["answer"],
#         "citations": result["citations"]
#     }

#     return {
#         "application_response": (
#             result["answer"]
#         ),

#         "application_citations": (
#             result["citations"]
#         ),

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # GENERAL CONVERSATION NODE
# # ============================================================

# def general_node(state: CuraTerraState):

#     query = state.get(
#         "user_query",
#         ""
#     )

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     current_scheme = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     previous_outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     prompt = f"""
# You are CuraTera AI's general conversational assistant.

# Citizen profile:

# {json.dumps(
#     profile,
#     ensure_ascii=False,
#     default=str
# )}

# Current scheme:

# {current_scheme}

# Previous agent result:

# {json.dumps(
#     previous_outputs,
#     ensure_ascii=False,
#     default=str
# )}

# Current user message:

# {query}

# Respond naturally.

# Rules:

# 1. Handle greetings naturally.
# 2. Handle thanks and acknowledgements naturally.
# 3. Handle casual conversation naturally.
# 4. Answer general knowledge questions.
# 5. Answer programming and coding questions.
# 6. Do not make eligibility decisions.
# 7. Do not invent government scheme facts.
# 8. Do not invent benefits, documents, or application steps.
# 9. Do not mention internal agents, planners, tools,
#    or implementation details.
# 10. Match the user's language.
# 11. Keep the response concise and useful.
# """

#     response = planner_model.invoke(
#         [
#             HumanMessage(
#                 content=prompt
#             )
#         ]
#     )

#     answer = response.content

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["general"] = {
#         "answer": answer,
#         "citations": []
#     }

#     return {
#         "general_response": answer,

#         "agent_outputs": outputs,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         ),

#         "final_response": answer,
#     }


# # ============================================================
# # CLARIFICATION NODE
# # ============================================================

# def clarification_node(state: CuraTerraState):

#     current_scheme = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     if current_scheme:

#         message = (
#             f"Are you referring to scheme "
#             f"{current_scheme}?"
#         )

#     else:

#         message = (
#             "Which government scheme are you "
#             "referring to? Please provide the "
#             "scheme ID, such as S020 or S039."
#         )

#     outputs = dict(
#         state.get(
#             "agent_outputs",
#             {}
#         )
#     )

#     outputs["clarification"] = {
#         "answer": message,
#         "citations": []
#     }

#     return {
#         "clarification_response": message,

#         "agent_outputs": outputs,

#         "final_response": message,

#         "task_index": (
#             state.get(
#                 "task_index",
#                 0
#             ) + 1
#         )
#     }


# # ============================================================
# # FALLBACK ROUTER
# # ============================================================

# def fallback_route_query(
#     state: CuraTerraState
# ) -> str:

#     query = (
#         state.get(
#             "user_query",
#             ""
#         )
#         .strip()
#         .lower()
#     )

#     eligibility_keywords = [
#         "eligible",
#         "eligibility",
#         "qualify",
#         "qualification",
#         "am i eligible",
#         "do i qualify",
#         "can i get"
#     ]

#     application_keywords = [
#         "how to apply",
#         "how do i apply",
#         "where to apply",
#         "application process",
#         "application form",
#         "application portal",
#         "portal",
#         "registration",
#         "register",
#         "documents required",
#         "what documents",
#         "document"
#     ]

#     recommendation_keywords = [
#         "recommend",
#         "recommendation",
#         "which scheme",
#         "best scheme",
#         "suitable scheme",
#         "which one",
#         "most relevant",
#         "what should i choose"
#     ]

#     rag_keywords = [
#         "benefit",
#         "benefits",
#         "details",
#         "scheme details",
#         "tell me about",
#         "what is this scheme",
#         "scheme information",
#         "how much",
#         "amount",
#         "funding",
#         "rules",
#         "faq"
#     ]

#     if any(
#         keyword in query
#         for keyword in eligibility_keywords
#     ):
#         return "eligibility"

#     if any(
#         keyword in query
#         for keyword in application_keywords
#     ):
#         return "application"

#     if any(
#         keyword in query
#         for keyword in recommendation_keywords
#     ):
#         return "recommendation"

#     if any(
#         keyword in query
#         for keyword in rag_keywords
#     ):
#         return "rag"

#     return "general"


# # ============================================================
# # ALLOWED TASKS
# # ============================================================

# ALLOWED_TASKS = {
#     "eligibility",
#     "recommendation",
#     "rag",
#     "application",
#     "general",
#     "clarification",
# }


# # ============================================================
# # PLAN DEPENDENCY RESOLVER
# # ============================================================

# def resolve_plan(
#     tasks: list[str],
#     state: CuraTerraState,
#     scheme_reference: str | None
# ) -> list[str]:

#     cleaned = []

#     for task in tasks:

#         task = (
#             str(task)
#             .strip()
#             .lower()
#         )

#         if (
#             task in ALLOWED_TASKS
#             and task not in cleaned
#         ):
#             cleaned.append(task)

#     # --------------------------------------------------------
#     # Nothing recognized
#     # --------------------------------------------------------

#     if not cleaned:
#         return ["general"]

#     # --------------------------------------------------------
#     # Current scheme
#     # --------------------------------------------------------

#     current_scheme = normalize_scheme_id(
#         scheme_reference
#         or state.get(
#             "current_scheme_id"
#         )
#     )

#     # --------------------------------------------------------
#     # RAG / Application need a scheme
#     # --------------------------------------------------------

#     if (
#         (
#             "rag" in cleaned
#             or "application" in cleaned
#         )
#         and not current_scheme
#     ):
#         return ["clarification"]

#     # --------------------------------------------------------
#     # Recommendation needs eligibility
#     # --------------------------------------------------------

#     has_eligibility = bool(
#         state.get(
#             "eligibility_results"
#         )
#     )

#     if (
#         "recommendation" in cleaned
#         and not has_eligibility
#         and "eligibility" not in cleaned
#     ):

#         cleaned.append(
#             "eligibility"
#         )

#     # --------------------------------------------------------
#     # Execution priority
#     # --------------------------------------------------------

#     priority = {
#         "eligibility": 0,
#         "recommendation": 1,
#         "rag": 2,
#         "application": 3,
#         "general": 4,
#         "clarification": 5,
#     }

#     cleaned.sort(
#         key=lambda task: priority[task]
#     )

#     return cleaned


# # ============================================================
# # PLANNER NODE
# # ============================================================

# def planner_node(state: CuraTerraState):

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     current_scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#     )

#     previous_outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     eligibility_exists = bool(
#         state.get(
#             "eligibility_results"
#         )
#     )

#     recommendation_exists = bool(
#         state.get(
#             "recommendations"
#         )
#     )

#     prompt = f"""
# Current citizen profile:

# {json.dumps(
#     profile,
#     indent=2,
#     ensure_ascii=False,
#     default=str
# )}

# Current scheme:

# {current_scheme_id}

# Previous agent outputs:

# {json.dumps(
#     previous_outputs,
#     indent=2,
#     ensure_ascii=False,
#     default=str
# )}

# Previous eligibility result exists:
# {eligibility_exists}

# Previous recommendation exists:
# {recommendation_exists}

# Current user message:

# {user_query}

# Create the smallest correct execution plan.

# Important:

# - Understand the user's current message using context.
# - If the user says "this scheme", "that scheme", "it",
#   "tell me more", "which one", etc., use current scheme
#   context when available.
# - If no scheme exists and the user asks for scheme-specific
#   benefits, documents, details, or application information,
#   use clarification.
# - Never guess a scheme.
# - Do not add eligibility or recommendation just because
#   application has no scheme.
# - Use general for greetings, thanks, acknowledgements,
#   casual conversation, coding, programming, or unrelated
#   questions.
# - Multiple tasks are allowed.
# - Do not answer the user.
# - Do not return profile.
# """

#     try:

#         response = planner_agent.invoke(
#             {
#                 "messages": [
#                     HumanMessage(
#                         content=prompt
#                     )
#                 ]
#             }
#         )

#         structured = response[
#             "structured_response"
#         ]

#         raw_tasks = list(
#             structured.tasks
#         )

#         scheme_reference = normalize_scheme_id(
#             structured.scheme_reference
#             or current_scheme_id
#         )

#         primary_task = (
#             structured.primary_task
#             or (
#                 raw_tasks[0]
#                 if raw_tasks
#                 else "general"
#             )
#         )

#     except Exception as error:

#         print(
#             "\n[PLANNER WARNING]",
#             error
#         )

#         fallback_task = fallback_route_query(
#             state
#         )

#         raw_tasks = [
#             fallback_task
#         ]

#         scheme_reference = (
#             current_scheme_id
#         )

#         primary_task = fallback_task

#     planned_tasks = resolve_plan(
#         raw_tasks,
#         state,
#         scheme_reference
#     )

#     print("\n[PLANNER]")
#     print(
#         "User query:",
#         user_query
#     )

#     print(
#         "Raw tasks:",
#         raw_tasks
#     )

#     print(
#         "Resolved tasks:",
#         planned_tasks
#     )

#     print(
#         "Scheme reference:",
#         scheme_reference
#     )

#     return {
#         "planned_tasks": planned_tasks,

#         "task_index": 0,

#         "router_intent": primary_task,

#         "scheme_reference": scheme_reference,

#         "current_scheme_id": scheme_reference,

#         "execution_mode": "normal_query",

#         "agent_outputs": {},

#         "profile_changed": False,
#     }


# # ============================================================
# # START ROUTING
# # ============================================================

# def route_from_start(
#     state: CuraTerraState
# ) -> str:

#     if state.get(
#         "profile_complete",
#         False
#     ):
#         return "planner"

#     return "profile"


# # ============================================================
# # AFTER PROFILE
# # ============================================================

# def route_after_profile(
#     state: CuraTerraState
# ) -> str:

#     if not state.get(
#         "profile_valid",
#         True
#     ):
#         return "end"

#     if state.get(
#         "profile_complete",
#         False
#     ):
#         return "eligibility"

#     return "end"


# # ============================================================
# # NEXT TASK
# # ============================================================

# def route_next_task(
#     state: CuraTerraState
# ) -> str:

#     tasks = state.get(
#         "planned_tasks",
#         []
#     )

#     index = state.get(
#         "task_index",
#         0
#     )

#     if index >= len(tasks):
#         return "finalize"

#     return tasks[index]


# # ============================================================
# # AFTER ELIGIBILITY
# # ============================================================

# def route_after_eligibility(
#     state: CuraTerraState
# ) -> str:

#     if (
#         state.get(
#             "execution_mode"
#         )
#         == "profile_completion"
#     ):
#         return "recommendation"

#     return route_next_task(
#         state
#     )


# # ============================================================
# # AFTER RECOMMENDATION
# # ============================================================

# def route_after_recommendation(
#     state: CuraTerraState
# ) -> str:

#     if (
#         state.get(
#             "execution_mode"
#         )
#         == "profile_completion"
#     ):
#         return "finalize"

#     return route_next_task(
#         state
#     )


# # ============================================================
# # FINAL RESPONSE AGENT
# # ============================================================

# def finalize_node(
#     state: CuraTerraState
# ):

#     outputs = state.get(
#         "agent_outputs",
#         {}
#     )

#     user_query = state.get(
#         "user_query",
#         ""
#     )

#     profile = state.get(
#         "citizen_profile",
#         {}
#     )

#     scheme_id = normalize_scheme_id(
#         state.get(
#             "current_scheme_id"
#         )
#         or state.get(
#             "scheme_reference"
#         )
#     )

#     # --------------------------------------------------------
#     # No specialist output
#     # --------------------------------------------------------

#     if not outputs:

#         existing_response = state.get(
#             "final_response"
#         )

#         if existing_response:

#             return {
#                 "final_response": {
#                     "message": existing_response,
#                     "blocks": [],
#                     "citations": [],
#                     "profile": profile,
#                     "metadata": {
#                         "intent": "profile",
#                         "scheme_id": scheme_id,
#                         "language": "English"
#                     }
#                 }
#             }

#         response = generate_response(
#             task="general",
#             user_query=user_query,
#             specialist_result={},
#             profile=profile,
#             scheme_id=scheme_id,
#             citations=[]
#         )

#         return {
#             "final_response": response.model_dump()
#         }

#     # --------------------------------------------------------
#     # Determine task
#     # --------------------------------------------------------

#     tasks = state.get(
#         "planned_tasks",
#         []
#     )

#     if len(tasks) == 1:

#         response_task = tasks[0]

#     else:

#         response_task = "multi"

#     # --------------------------------------------------------
#     # Collect citations
#     # --------------------------------------------------------

#     citations = []

#     for output in outputs.values():

#         if not isinstance(
#             output,
#             dict
#         ):
#             continue

#         output_citations = output.get(
#             "citations",
#             []
#         )

#         if output_citations:
#             citations.extend(
#                 output_citations
#             )

#     # --------------------------------------------------------
#     # Remove duplicate citations
#     # --------------------------------------------------------

#     unique_citations = []

#     seen = set()

#     for citation in citations:

#         citation_key = str(
#             citation
#         )

#         if citation_key not in seen:

#             seen.add(
#                 citation_key
#             )

#             unique_citations.append(
#                 citation
#             )

#     # --------------------------------------------------------
#     # Response Agent
#     # --------------------------------------------------------

#     response = generate_response(
#         task=response_task,
#         user_query=user_query,
#         specialist_result=outputs,
#         profile=profile,
#         scheme_id=scheme_id,
#         citations=unique_citations
#     )

#     print(
#         "\n[RESPONSE AGENT]"
#     )

#     print(
#         "Task:",
#         response_task
#     )

#     print(
#         "Final message generated."
#     )

#     return {
#         "final_response": response.model_dump()
#     }


# # ============================================================
# # BUILD GRAPH
# # ============================================================

# def build_graph():

#     builder = StateGraph(
#         CuraTerraState
#     )

#     # --------------------------------------------------------
#     # Nodes
#     # --------------------------------------------------------

#     builder.add_node(
#         "profile",
#         profile_node
#     )

#     builder.add_node(
#         "planner",
#         planner_node
#     )

#     builder.add_node(
#         "eligibility",
#         eligibility_node
#     )

#     builder.add_node(
#         "recommendation",
#         recommendation_node
#     )

#     builder.add_node(
#         "rag",
#         rag_node
#     )

#     builder.add_node(
#         "application",
#         application_node
#     )

#     builder.add_node(
#         "general",
#         general_node
#     )

#     builder.add_node(
#         "clarification",
#         clarification_node
#     )

#     builder.add_node(
#         "finalize",
#         finalize_node
#     )

#     # --------------------------------------------------------
#     # START
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         START,
#         route_from_start,
#         {
#             "profile": "profile",
#             "planner": "planner",
#         }
#     )

#     # --------------------------------------------------------
#     # PROFILE
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "profile",
#         route_after_profile,
#         {
#             "eligibility": "eligibility",
#             "end": END,
#         }
#     )

#     # --------------------------------------------------------
#     # PLANNER
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "planner",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # ELIGIBILITY
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "eligibility",
#         route_after_eligibility,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # RECOMMENDATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "recommendation",
#         route_after_recommendation,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # RAG
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "rag",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # APPLICATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "application",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # GENERAL
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "general",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # CLARIFICATION
#     # --------------------------------------------------------

#     builder.add_conditional_edges(
#         "clarification",
#         route_next_task,
#         {
#             "eligibility": "eligibility",
#             "recommendation": "recommendation",
#             "rag": "rag",
#             "application": "application",
#             "general": "general",
#             "clarification": "clarification",
#             "finalize": "finalize",
#         }
#     )

#     # --------------------------------------------------------
#     # FINALIZE
#     # --------------------------------------------------------

#     builder.add_edge(
#         "finalize",
#         END
#     )

#     # --------------------------------------------------------
#     # CHECKPOINTER
#     # --------------------------------------------------------

#     return builder.compile(
#         checkpointer=checkpointer
#     )











## 3 


import json
import re

from langchain.messages import HumanMessage
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

from agents.state import CuraTerraState
from schemas import QueryPlan
from memory.checkpointer import checkpointer

from agents.profile_agent import get_profile_agent_response
from agents.eligibility_agent import get_eligibility_agent_response
from agents.recommendation_agent import get_recommendation_response
from agents.rag_agent import get_rag_response
from agents.application_agent import get_application_response
from agents.response_agent import generate_response


# ============================================================
# MODEL
# ============================================================

planner_model = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


# ============================================================
# QUERY PLANNER
# ============================================================

planner_system_prompt = """
You are CuraTera's Context-Aware Query Planner.

Your ONLY job is to understand the citizen's CURRENT message
and create the smallest correct execution plan.

You are a ROUTER, not the final answer generator.

Use:
- current citizen profile
- current scheme
- previous conversation/agent outputs
- current user message

AVAILABLE TASKS:

1. eligibility
Use when the user asks:
- Am I eligible?
- Do I qualify?
- Which schemes can I get?
- Can I get this scheme?
- Check my eligibility.

2. recommendation
Use when the user asks:
- Which scheme is best?
- Which scheme is suitable?
- What do you recommend?
- Which one should I choose?

3. rag
Use for verified scheme information:
- benefits
- scheme details
- scheme rules
- scheme explanation
- amount/funding
- coverage
- FAQs

4. application
Use for:
- how to apply
- where to apply
- application process
- portal
- registration
- required documents
- application steps

5. general
Use for:
- greetings
- thanks
- acknowledgements
- casual conversation
- general knowledge
- programming
- coding
- unrelated questions
- simple clarification
- normal conversation

6. clarification
Use when the user asks about a scheme-specific subject
but there is NO explicit scheme and NO current scheme context.

Examples:
"What are the benefits of this scheme?"
"How do I apply for it?"
"What documents are needed?"
when no scheme has been established.

IMPORTANT CONTEXT RULES:

If the user explicitly mentions a scheme, extract it.

Examples:
"S039"       -> scheme_reference = S039
"scheme 20"  -> scheme_reference = S020
"S01"        -> scheme_reference = S001
"S1"         -> scheme_reference = S001

If the user says:
- this scheme
- that scheme
- it
- this
- that one
- tell me more

and a current scheme exists, use that current scheme.

Examples:

Current scheme = S039
User: "tell me more"
-> ["rag"]

Current scheme = S039
User: "how do I apply?"
-> ["application"]

Current scheme = S039
User: "what documents do I need?"
-> ["application"]

Current scheme = S039
User: "okay thank you"
-> ["general"]

If there is NO current scheme and the user says:
"how do I apply for this?"
-> ["clarification"]

If there is NO current scheme and the user says:
"what are the benefits of this scheme?"
-> ["clarification"]

NEVER guess a scheme.

NEVER send an unknown scheme-specific question
to RAG across all schemes.

NEVER add eligibility or recommendation merely because
an application query has no scheme.

Multiple tasks are allowed.

Never return "profile" as a task.
Never answer the user yourself.
"""


planner_agent = create_agent(
    model=planner_model,
    system_prompt=planner_system_prompt,
    tools=[],
    response_format=QueryPlan,
)


# ============================================================
# PROFILE COMPLETENESS
# ============================================================

CORE_PROFILE_FIELDS = [
    "age",
    "state",
    "district",
    "gender",
    "social_category",
    "annual_family_income",
    "occupation",
]


def check_profile_completeness(profile: dict):

    missing = []

    for field in CORE_PROFILE_FIELDS:

        value = profile.get(field)

        if value is None:
            missing.append(field)

        elif isinstance(value, str) and not value.strip():
            missing.append(field)

    return len(missing) == 0, missing


# ============================================================
# SCHEME ID NORMALIZATION
# ============================================================

def normalize_scheme_id(scheme_id):

    if scheme_id is None:
        return None

    scheme_id = str(
        scheme_id
    ).strip().upper()

    if not scheme_id:
        return None

    # 20 -> S020
    if scheme_id.isdigit():
        return f"S{int(scheme_id):03d}"

    # S20 -> S020
    if scheme_id.startswith("S"):

        number = scheme_id[1:]

        if number.isdigit():
            return f"S{int(number):03d}"

    return scheme_id


# ============================================================
# PROFILE NODE
# ============================================================

def profile_node(state: CuraTerraState):

    user_query = state.get(
        "user_query",
        ""
    )

    current_profile = state.get(
        "citizen_profile",
        {}
    )

    result = get_profile_agent_response(
        user_input=user_query,
        current_profile=current_profile
    )

    old_profile = current_profile

    new_profile = result.get(
        "profile",
        {}
    )

    profile_changed = (
        old_profile != new_profile
    )

    profile_complete, missing_information = (
        check_profile_completeness(
            new_profile
        )
    )

    print("\n[PROFILE DEBUG]")

    print(
        "Extracted profile:",
        new_profile
    )

    print(
        "LLM profile_complete:",
        result.get(
            "profile_complete"
        )
    )

    print(
        "Python profile_complete:",
        profile_complete
    )

    print(
        "Missing fields:",
        missing_information
    )

    # --------------------------------------------------------
    # Incomplete profile
    #
    # Store profile response so finalize can send it through
    # the Response Agent.
    # --------------------------------------------------------

    if not profile_complete:

        profile_outputs = {
            "profile": {
                "answer": result.get(
                    "response",
                    ""
                ),
                "citations": []
            }
        }

        return {
            "citizen_profile": new_profile,

            "profile_complete": profile_complete,

            "profile_changed": profile_changed,

            "profile_valid": result.get(
                "profile_valid",
                True
            ),

            "missing_information": (
                missing_information
            ),

            "validation_issues": result.get(
                "validation_issues",
                []
            ),

            "execution_mode": (
                "profile_completion"
            ),

            "agent_outputs": profile_outputs,

            "planned_tasks": [],

            "task_index": 0,
        }

    # --------------------------------------------------------
    # Profile complete
    #
    # Existing architecture intentionally continues to:
    # Profile -> Eligibility -> Recommendation
    # --------------------------------------------------------

    return {
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

        "execution_mode": (
            "profile_completion"
        ),

        "agent_outputs": {},

        "planned_tasks": [],

        "task_index": 0,
    }


# ============================================================
# ELIGIBILITY NODE
# ============================================================

def eligibility_node(state: CuraTerraState):

    profile = state.get(
        "citizen_profile",
        {}
    )

    result = get_eligibility_agent_response(
        profile
    )

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["eligibility"] = {
        "answer": result,
        "citations": []
    }

    return {
        "eligibility_results": result,

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        ),
    }


# ============================================================
# RECOMMENDATION NODE
# ============================================================

def recommendation_node(state: CuraTerraState):

    profile = state.get(
        "citizen_profile",
        {}
    )

    eligibility_results = state.get(
        "eligibility_results"
    )

    recommendation_input = {
        "citizen_profile": profile,
        "eligibility_results": eligibility_results
    }

    result = get_recommendation_response(
        str(recommendation_input)
    )

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["recommendation"] = result

    top_scheme_id = None

    if isinstance(result, dict):

        top_scheme_id = result.get(
            "top_scheme_id"
        )

        answer = result.get(
            "answer",
            str(result)
        )

    else:

        answer = str(result)

        match = re.search(
            r"\bS\d{1,3}\b",
            answer.upper()
        )

        if match:
            top_scheme_id = match.group(0)

    top_scheme_id = normalize_scheme_id(
        top_scheme_id
    )

    return {
        "recommendations": result,

        "current_scheme_id": (
            top_scheme_id
            or state.get(
                "current_scheme_id"
            )
        ),

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        ),
    }


# ============================================================
# RAG NODE
# ============================================================

def rag_node(state: CuraTerraState):

    query = state.get(
        "user_query",
        ""
    )

    scheme_id = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
        or state.get(
            "scheme_reference"
        )
    )

    print("\n[RAG]")

    print(
        "Query:",
        query
    )

    print(
        "Scheme ID:",
        scheme_id
    )

    result = get_rag_response(
        query=query,
        retrieval_k=10,
        final_k=5,
        scheme_id=scheme_id
    )

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["rag"] = {
        "answer": result["answer"],
        "citations": result["citations"]
    }

    return {
        "rag_response": result["answer"],

        "rag_citations": result["citations"],

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        )
    }


# ============================================================
# APPLICATION NODE
# ============================================================

def application_node(state: CuraTerraState):

    query = state.get(
        "user_query",
        ""
    )

    scheme_id = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
        or state.get(
            "scheme_reference"
        )
    )

    print("\n[APPLICATION]")

    print(
        "Query:",
        query
    )

    print(
        "Scheme ID:",
        scheme_id
    )

    result = get_application_response(
        query=query,
        retrieval_k=10,
        final_k=5,
        scheme_id=scheme_id
    )

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["application"] = {
        "answer": result["answer"],
        "citations": result["citations"]
    }

    return {
        "application_response": (
            result["answer"]
        ),

        "application_citations": (
            result["citations"]
        ),

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        )
    }


# ============================================================
# GENERAL CONVERSATION NODE
# ============================================================

def general_node(state: CuraTerraState):

    query = state.get(
        "user_query",
        ""
    )

    profile = state.get(
        "citizen_profile",
        {}
    )

    current_scheme = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
        or state.get(
            "scheme_reference"
        )
    )

    previous_outputs = state.get(
        "agent_outputs",
        {}
    )

    recent_messages = state.get("messages", [])[-5:]
    messages_context = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_messages]) if recent_messages else "None"

    prompt = f"""
You are CuraTera AI's general conversational assistant.

Citizen profile:

{json.dumps(
    profile,
    ensure_ascii=False,
    default=str
)}

Current scheme:

{current_scheme}

Previous agent result:

{json.dumps(
    previous_outputs,
    ensure_ascii=False,
    default=str
)}

Recent conversation history:

{messages_context}

Current user message:

{query}

Respond naturally.

Rules:

1. Handle greetings naturally.
2. Handle thanks and acknowledgements naturally.
3. Handle casual conversation naturally.
4. Answer general knowledge questions.
5. Answer programming and coding questions.
6. Do not make eligibility decisions.
7. Do not invent government scheme facts.
8. Do not invent benefits, documents, or application steps.
9. Do not mention internal agents, planners, tools,
   or implementation details.
10. Match the user's language.
11. Keep the response concise and useful.
"""

    response = planner_model.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )

    answer = response.content

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["general"] = {
        "answer": answer,
        "citations": []
    }

    return {
        "general_response": answer,

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        )
    }


# ============================================================
# CLARIFICATION NODE
# ============================================================

def clarification_node(state: CuraTerraState):

    current_scheme = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
        or state.get(
            "scheme_reference"
        )
    )

    if current_scheme:

        message = (
            f"Are you referring to scheme "
            f"{current_scheme}?"
        )

    else:

        message = (
            "Which government scheme are you "
            "referring to? Please provide the "
            "scheme ID, such as S020 or S039."
        )

    outputs = dict(
        state.get(
            "agent_outputs",
            {}
        )
    )

    outputs["clarification"] = {
        "answer": message,
        "citations": []
    }

    return {
        "clarification_response": message,

        "agent_outputs": outputs,

        "task_index": (
            state.get(
                "task_index",
                0
            ) + 1
        )
    }


# ============================================================
# FALLBACK ROUTER
# ============================================================

def fallback_route_query(
    state: CuraTerraState
) -> str:

    query = (
        state.get(
            "user_query",
            ""
        )
        .strip()
        .lower()
    )

    eligibility_keywords = [
        "eligible",
        "eligibility",
        "qualify",
        "qualification",
        "am i eligible",
        "do i qualify",
        "can i get"
    ]

    application_keywords = [
        "how to apply",
        "how do i apply",
        "where to apply",
        "application process",
        "application form",
        "application portal",
        "portal",
        "registration",
        "register",
        "documents required",
        "what documents",
        "document"
    ]

    recommendation_keywords = [
        "recommend",
        "recommendation",
        "which scheme",
        "best scheme",
        "suitable scheme",
        "which one",
        "most relevant",
        "what should i choose"
    ]

    rag_keywords = [
        "benefit",
        "benefits",
        "details",
        "scheme details",
        "tell me about",
        "what is this scheme",
        "scheme information",
        "how much",
        "amount",
        "funding",
        "rules",
        "faq"
    ]

    if any(
        keyword in query
        for keyword in eligibility_keywords
    ):
        return "eligibility"

    if any(
        keyword in query
        for keyword in application_keywords
    ):
        return "application"

    if any(
        keyword in query
        for keyword in recommendation_keywords
    ):
        return "recommendation"

    if any(
        keyword in query
        for keyword in rag_keywords
    ):
        return "rag"

    return "general"


# ============================================================
# ALLOWED TASKS
# ============================================================

ALLOWED_TASKS = {
    "eligibility",
    "recommendation",
    "rag",
    "application",
    "general",
    "clarification",
}


# ============================================================
# PLAN DEPENDENCY RESOLVER
# ============================================================

def resolve_plan(
    tasks: list[str],
    state: CuraTerraState,
    scheme_reference: str | None
) -> list[str]:

    cleaned = []

    for task in tasks:

        task = (
            str(task)
            .strip()
            .lower()
        )

        if (
            task in ALLOWED_TASKS
            and task not in cleaned
        ):
            cleaned.append(task)

    # --------------------------------------------------------
    # Nothing recognized
    # --------------------------------------------------------

    if not cleaned:
        return ["general"]

    # --------------------------------------------------------
    # Current scheme
    # --------------------------------------------------------

    current_scheme = normalize_scheme_id(
        scheme_reference
        or state.get(
            "current_scheme_id"
        )
    )

    # --------------------------------------------------------
    # RAG / Application need a scheme
    # --------------------------------------------------------

    if (
        (
            "rag" in cleaned
            or "application" in cleaned
        )
        and not current_scheme
    ):
        return ["clarification"]

    # --------------------------------------------------------
    # Recommendation needs eligibility
    # --------------------------------------------------------

    has_eligibility = bool(
        state.get(
            "eligibility_results"
        )
    )

    if (
        "recommendation" in cleaned
        and not has_eligibility
        and "eligibility" not in cleaned
    ):

        cleaned.append(
            "eligibility"
        )

    # --------------------------------------------------------
    # Execution priority
    # --------------------------------------------------------

    priority = {
        "eligibility": 0,
        "recommendation": 1,
        "rag": 2,
        "application": 3,
        "general": 4,
        "clarification": 5,
    }

    cleaned.sort(
        key=lambda task: priority[task]
    )

    return cleaned


# ============================================================
# PLANNER NODE
# ============================================================

def planner_node(state: CuraTerraState):

    user_query = state.get(
        "user_query",
        ""
    )

    profile = state.get(
        "citizen_profile",
        {}
    )

    current_scheme_id = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
    )

    previous_outputs = state.get(
        "agent_outputs",
        {}
    )

    eligibility_exists = bool(
        state.get(
            "eligibility_results"
        )
    )

    recommendation_exists = bool(
        state.get(
            "recommendations"
        )
    )

    recent_messages = state.get("messages", [])[-5:]
    messages_context = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_messages]) if recent_messages else "None"

    prompt = f"""
Current citizen profile:

{json.dumps(
    profile,
    indent=2,
    ensure_ascii=False,
    default=str
)}

Current scheme:

{current_scheme_id}

Previous agent outputs:

{json.dumps(
    previous_outputs,
    indent=2,
    ensure_ascii=False,
    default=str
)}

Previous eligibility result exists:
{eligibility_exists}

Previous recommendation exists:
{recommendation_exists}

Recent conversation history:
{messages_context}

Current user message:

{user_query}

Create the smallest correct execution plan.

Important:

- Understand the user's current message using context.
- If the user says "this scheme", "that scheme", "it",
  "tell me more", "which one", etc., use current scheme
  context when available.
- If no scheme exists and the user asks for scheme-specific
  benefits, documents, details, or application information,
  use clarification.
- Never guess a scheme.
- Do not add eligibility or recommendation just because
  application has no scheme.
- Use general for greetings, thanks, acknowledgements,
  casual conversation, coding, programming, or unrelated
  questions.
- Multiple tasks are allowed.
- Do not answer the user.
- Do not return profile.
"""

    try:

        response = planner_agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=prompt
                    )
                ]
            }
        )

        structured = response[
            "structured_response"
        ]

        raw_tasks = list(
            structured.tasks
        )

        scheme_reference = normalize_scheme_id(
            structured.scheme_reference
            or current_scheme_id
        )

        primary_task = (
            structured.primary_task
            or (
                raw_tasks[0]
                if raw_tasks
                else "general"
            )
        )

    except Exception as error:

        print(
            "\n[PLANNER WARNING]",
            error
        )

        fallback_task = fallback_route_query(
            state
        )

        raw_tasks = [
            fallback_task
        ]

        scheme_reference = (
            current_scheme_id
        )

        primary_task = fallback_task

    planned_tasks = resolve_plan(
        raw_tasks,
        state,
        scheme_reference
    )

    print("\n[PLANNER]")

    print(
        "User query:",
        user_query
    )

    print(
        "Raw tasks:",
        raw_tasks
    )

    print(
        "Resolved tasks:",
        planned_tasks
    )

    print(
        "Scheme reference:",
        scheme_reference
    )

    return {
        "planned_tasks": planned_tasks,

        "task_index": 0,

        "router_intent": primary_task,

        "scheme_reference": scheme_reference,

        "current_scheme_id": scheme_reference,

        "execution_mode": "normal_query",

        "agent_outputs": {},

        "profile_changed": False,
    }


# ============================================================
# START ROUTING
# ============================================================

def route_from_start(
    state: CuraTerraState
) -> str:

    if state.get(
        "profile_complete",
        False
    ):
        return "planner"

    return "profile"


# ============================================================
# AFTER PROFILE
# ============================================================

def route_after_profile(
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


# ============================================================
# NEXT TASK
# ============================================================

def route_next_task(
    state: CuraTerraState
) -> str:

    tasks = state.get(
        "planned_tasks",
        []
    )

    index = state.get(
        "task_index",
        0
    )

    if index >= len(tasks):
        return "finalize"

    return tasks[index]


# ============================================================
# AFTER ELIGIBILITY
# ============================================================

def route_after_eligibility(
    state: CuraTerraState
) -> str:

    # --------------------------------------------------------
    # Existing intended behavior:
    # completing the profile triggers:
    # Eligibility -> Recommendation
    # --------------------------------------------------------

    if (
        state.get(
            "execution_mode"
        )
        == "profile_completion"
    ):
        return "recommendation"

    return route_next_task(
        state
    )


# ============================================================
# AFTER RECOMMENDATION
# ============================================================

def route_after_recommendation(
    state: CuraTerraState
) -> str:

    # --------------------------------------------------------
    # Existing intended behavior:
    # profile completion flow finishes after recommendation.
    # --------------------------------------------------------

    if (
        state.get(
            "execution_mode"
        )
        == "profile_completion"
    ):
        return "finalize"

    return route_next_task(
        state
    )


# ============================================================
# FINAL RESPONSE AGENT
# ============================================================

def finalize_node(
    state: CuraTerraState
):

    outputs = state.get(
        "agent_outputs",
        {}
    )

    user_query = state.get(
        "user_query",
        ""
    )

    profile = state.get(
        "citizen_profile",
        {}
    )

    scheme_id = normalize_scheme_id(
        state.get(
            "current_scheme_id"
        )
        or state.get(
            "scheme_reference"
        )
    )

    tasks = state.get(
        "planned_tasks",
        []
    )

    # --------------------------------------------------------
    # Determine response task
    # --------------------------------------------------------

    if tasks:

        if len(tasks) == 1:

            response_task = tasks[0]

        else:

            response_task = "multi"

    else:

        # Incomplete profile / profile-only response
        if not state.get(
            "profile_complete",
            False
        ):

            response_task = "profile"

        # Completed profile automatically produced eligibility
        # and recommendation outputs.
        else:

            response_task = "multi"

    # --------------------------------------------------------
    # Collect citations
    # --------------------------------------------------------

    citations = []

    for output in outputs.values():

        if not isinstance(
            output,
            dict
        ):
            continue

        output_citations = output.get(
            "citations",
            []
        )

        if output_citations:
            citations.extend(
                output_citations
            )

    # --------------------------------------------------------
    # Remove duplicate citations
    # --------------------------------------------------------

    unique_citations = []

    seen = set()

    for citation in citations:

        citation_key = str(
            citation
        )

        if citation_key not in seen:

            seen.add(
                citation_key
            )

            unique_citations.append(
                citation
            )

    # --------------------------------------------------------
    # Response Agent
    # --------------------------------------------------------

    recent_messages = state.get("messages", [])[-5:]

    response = generate_response(
        task=response_task,
        user_query=user_query,
        specialist_result=outputs,
        profile=profile,
        scheme_id=scheme_id,
        citations=unique_citations,
        messages=recent_messages
    )

    print("\n[RESPONSE AGENT]")

    print(
        "Task:",
        response_task
    )

    print(
        "Final message generated."
    )

    final_resp_dict = response.model_dump()
    
    return {
        "final_response": final_resp_dict,
        "messages": [
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": final_resp_dict.get("message", str(final_resp_dict))}
        ]
    }


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph():

    builder = StateGraph(
        CuraTerraState
    )

    # --------------------------------------------------------
    # Nodes
    # --------------------------------------------------------

    builder.add_node(
        "profile",
        profile_node
    )

    builder.add_node(
        "planner",
        planner_node
    )

    builder.add_node(
        "eligibility",
        eligibility_node
    )

    builder.add_node(
        "recommendation",
        recommendation_node
    )

    builder.add_node(
        "rag",
        rag_node
    )

    builder.add_node(
        "application",
        application_node
    )

    builder.add_node(
        "general",
        general_node
    )

    builder.add_node(
        "clarification",
        clarification_node
    )

    builder.add_node(
        "finalize",
        finalize_node
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "profile": "profile",
            "planner": "planner",
        }
    )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "profile",
        route_after_profile,
        {
            "eligibility": "eligibility",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # PLANNER
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "planner",
        route_next_task,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # ELIGIBILITY
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "eligibility",
        route_after_eligibility,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # RECOMMENDATION
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "rag",
        route_next_task,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # APPLICATION
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "application",
        route_next_task,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # GENERAL
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "general",
        route_next_task,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # CLARIFICATION
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "clarification",
        route_next_task,
        {
            "eligibility": "eligibility",
            "recommendation": "recommendation",
            "rag": "rag",
            "application": "application",
            "general": "general",
            "clarification": "clarification",
            "finalize": "finalize",
        }
    )

    # --------------------------------------------------------
    # FINALIZE
    # --------------------------------------------------------

    builder.add_edge(
        "finalize",
        END
    )

    # --------------------------------------------------------
    # CHECKPOINTER
    # --------------------------------------------------------

    return builder.compile(
        checkpointer=checkpointer
    )