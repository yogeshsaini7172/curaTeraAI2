from typing import Dict, Any

# Keys that belong to the CitizenProfile schema (what the profile agent uses).
# These are the canonical keys and should ALWAYS take priority over app aliases.
SCHEMA_KEYS = {
    'name', 'age', 'gender', 'state', 'district', 'rural_or_urban',
    'social_category', 'minority_status', 'disability_status', 'transgender_status',
    'annual_family_income', 'occupation', 'farmer_status', 'land_holding',
    'education_level', 'school_class', 'course', 'student_status',
    'employment_status', 'business_status', 'family_size', 'hostel_status',
    'continuous_study', 'income_tax_payer', 'special_conditions'
}

# App-specific alias keys that are NOT in the CitizenProfile schema.
# These get added during normalization for frontend compatibility.
APP_ALIAS_KEYS = {'annualIncome', 'category', 'education', 'fullName', 'village'}


def strip_to_schema_keys(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of the profile containing only CitizenProfile schema keys.
    Used before passing the profile to the profile agent so the LLM doesn't
    echo back stale alias values it doesn't understand.
    """
    if not isinstance(profile, dict):
        return {}
    return {k: v for k, v in profile.items() if k in SCHEMA_KEYS}


def normalize_and_unify_profile(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes profile keys across LangGraph citizen_profile and App Profile representations
    so that both systems share a 100% unified profile state.

    IMPORTANT: Schema keys (annual_family_income, social_category, education_level, name)
    always take priority over app alias keys (annualIncome, category, education, fullName).
    This ensures that when the profile agent updates a schema key, the stale alias
    value does not overwrite it.
    """
    if not isinstance(raw_profile, dict):
        return {}

    unified = {}
    
    # Filter out empty or null values and protected fields
    protected_keys = {'username', 'password', '_id', 'userId', 'id'}
    for k, v in raw_profile.items():
        if k in protected_keys:
            continue
        if v is None or v == '' or v == 'null':
            continue
        unified[k] = v

    # 1. social_category (schema) <-> category (app alias)
    # Schema key takes priority
    schema_val = unified.get('social_category')
    alias_val = unified.get('category')
    winner = schema_val if schema_val is not None else alias_val
    if winner is not None:
        unified['social_category'] = str(winner).strip()
        unified['category'] = str(winner).strip()

    # 2. annual_family_income (schema) <-> annualIncome (app alias)
    # Schema key takes priority
    schema_val = unified.get('annual_family_income')
    alias_val = unified.get('annualIncome')
    winner = schema_val if schema_val is not None else alias_val
    if winner is not None:
        unified['annual_family_income'] = winner
        unified['annualIncome'] = winner

    # 3. education_level (schema) <-> education (app alias)
    # Schema key takes priority
    schema_val = unified.get('education_level')
    alias_val = unified.get('education')
    winner = schema_val if schema_val is not None else alias_val
    if winner is not None:
        unified['education_level'] = str(winner).strip()
        unified['education'] = str(winner).strip()

    # 4. name (schema) <-> fullName (app alias)
    # Schema key takes priority. Ensure username/email is never treated as full name.
    schema_val = unified.get('name')
    alias_val = unified.get('fullName')
    winner = schema_val if schema_val is not None else alias_val
    if winner and '@' not in str(winner):
        unified['name'] = str(winner).strip()
        unified['fullName'] = str(winner).strip()

    # 5. Age normalization (ensure consistent string)
    if 'age' in unified:
        unified['age'] = str(unified['age']).strip()

    # 6. Village / Rural or Urban
    village = unified.get('village') or unified.get('rural_or_urban')
    if village:
        unified['village'] = str(village).strip()
        if 'rural_or_urban' not in unified:
            unified['rural_or_urban'] = str(village).strip()

    return unified


def get_unified_profile(graph, email: str, users_collection=None) -> Dict[str, Any]:
    """
    Retrieves the unified citizen profile directly from LangGraph state.
    LangGraph is the single source of truth for profile data.
    """
    config = {
        "configurable": {
            "thread_id": email
        }
    }

    lg_profile = {}
    try:
        state = graph.get_state(config)
        if state and state.values:
            lg_profile = state.values.get("citizen_profile", {}) or {}
    except Exception as e:
        print(f"[ProfileHelper] Warning reading LangGraph state for {email}: {e}")

    unified = normalize_and_unify_profile(lg_profile)

    # Sync back to LangGraph state if normalization changed it
    if unified != lg_profile:
        try:
            graph.update_state(config, {"citizen_profile": unified})
        except Exception as e:
            print(f"[ProfileHelper] Warning syncing LangGraph state for {email}: {e}")

    return unified


def update_unified_profile(graph, email: str, new_data: Dict[str, Any], users_collection=None) -> Dict[str, Any]:
    """
    Updates the citizen profile in LangGraph state only.
    """
    config = {
        "configurable": {
            "thread_id": email
        }
    }

    # Fetch current unified profile
    current_unified = get_unified_profile(graph, email)

    # Map frontend alias keys to schema keys in new_data BEFORE merging.
    # Otherwise, the old schema key in current_unified will override the new alias key
    # due to the schema-first priority in normalize_and_unify_profile.
    if 'annualIncome' in new_data:
        new_data['annual_family_income'] = new_data['annualIncome']
    if 'category' in new_data:
        new_data['social_category'] = new_data['category']
    if 'education' in new_data:
        new_data['education_level'] = new_data['education']
    if 'fullName' in new_data:
        new_data['name'] = new_data['fullName']

    # Merge incoming new data
    merged = {**current_unified, **new_data}
    unified = normalize_and_unify_profile(merged)

    # Update LangGraph state
    try:
        graph.update_state(config, {"citizen_profile": unified})
    except Exception as e:
        print(f"[ProfileHelper] Error updating LangGraph state for {email}: {e}")

    return unified
