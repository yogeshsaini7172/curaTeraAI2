from typing import Optional, Literal
from pydantic import BaseModel, Field


class CitizenProfile(BaseModel):
    name: Optional[str] = None

    age: Optional[int] = None
    gender: Optional[str] = None

    state: Optional[str] = None
    district: Optional[str] = None
    rural_or_urban: Optional[str] = None

    social_category: Optional[str] = None
    minority_status: Optional[bool] = None
    disability_status: Optional[bool] = None
    transgender_status: Optional[bool] = None

    annual_family_income: Optional[str] = None

    occupation: Optional[str] = None
    farmer_status: Optional[bool] = None
    land_holding: Optional[str] = None

    education_level: Optional[str] = None
    school_class: Optional[int] = None
    course: Optional[str] = None
    student_status: Optional[bool] = None

    employment_status: Optional[str] = None
    business_status: Optional[bool] = None

    family_size: Optional[int] = None
    hostel_status: Optional[bool] = None
    continuous_study: Optional[bool] = None
    income_tax_payer: Optional[bool] = None

    special_conditions: Optional[list[str]] = None


class ProfileAgentOutput(BaseModel):
    profile: CitizenProfile
    profile_complete: bool = False
    profile_valid: bool = True
    missing_information: list[str] = Field(
        default_factory=list
    )
    validation_issues: list[str] = Field(
        default_factory=list
    )
    response: str


class QueryPlan(BaseModel):
    tasks: list[
        Literal[
            "eligibility",
            "recommendation",
            "rag",
            "application",
            "general",
            "clarification",
        ]
    ] = Field(
        default_factory=list
    )

    primary_task: (
        Literal[
            "eligibility",
            "recommendation",
            "rag",
            "application",
            "general",
            "clarification",
        ]
        | None
    ) = None

    scheme_reference: str | None = None