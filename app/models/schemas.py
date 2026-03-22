"""Pydantic v2 schemas for JananiSuraksha API request/response validation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    BloodBankStatus,
    CapabilityLevel,
    ComplicationHistory,
    FacilityType,
    InterventionUrgency,
    RiskLevel,
)


class RiskFactors(BaseModel):
    age: int = Field(ge=12, le=55)
    parity: int = Field(ge=0, le=15)
    hemoglobin: float = Field(ge=3.0, le=20.0, description="Hemoglobin in g/dL")
    bp_systolic: int = Field(ge=60, le=250)
    bp_diastolic: int = Field(ge=30, le=160)
    # Max 42 weeks per ACOG Practice Bulletin No. 146 (2014): post-term pregnancies require immediate clinical management
    gestational_weeks: int = Field(ge=1, le=42)
    height_cm: float = Field(ge=100, le=220)
    weight_kg: float = Field(ge=25, le=200)
    complication_history: ComplicationHistory

    @field_validator("bp_diastolic")
    @classmethod
    def diastolic_less_than_systolic(cls, v: int, info) -> int:
        systolic = info.data.get("bp_systolic")
        if systolic is not None and v >= systolic:
            raise ValueError(
                f"bp_diastolic ({v}) must be less than bp_systolic ({systolic})"
            )
        return v


class RiskResult(BaseModel):
    risk_score: float
    risk_level: RiskLevel
    alpha: float
    beta: float
    interventions: list[str]
    risk_factors_summary: dict[str, str]


class ReferralRequest(BaseModel):
    latitude: float = Field(ge=6.0, le=38.0, description="Latitude within India bounds")
    longitude: float = Field(ge=68.0, le=98.0, description="Longitude within India bounds")
    capability_required: CapabilityLevel
    risk_level: RiskLevel


class ReferralResult(BaseModel):
    facility_name: str
    facility_type: FacilityType
    distance_km: float
    eta_minutes: float
    specialist_available: bool
    blood_bank_status: BloodBankStatus
    has_functional_ot: bool
    contact_phone: str
    backup_facility: Optional[ReferralResult] = None

    model_config = {"from_attributes": True}


class AnemiaInput(BaseModel):
    initial_hb: float = Field(ge=3.0, le=20.0, description="Initial hemoglobin in g/dL")
    # Max 42 weeks per ACOG Practice Bulletin No. 146 (2014): post-term pregnancies require immediate clinical management
    gestational_weeks: int = Field(ge=1, le=42)
    ifa_compliance: float = Field(ge=0.0, le=1.0, description="IFA tablet compliance rate")
    dietary_score: float = Field(ge=0.0, le=1.0)
    prev_anemia: bool


class AnemiaResult(BaseModel):
    current_hb: float
    predicted_delivery_hb: float
    trajectory: list[dict]
    risk_level: RiskLevel
    intervention_urgency: InterventionUrgency
    compliance_impact: dict


class AssessmentRequest(BaseModel):
    mother_name: str = Field(min_length=1, max_length=200)
    asha_id: str = Field(min_length=1, max_length=50)
    risk_factors: RiskFactors
    latitude: float = Field(ge=6.0, le=38.0)
    longitude: float = Field(ge=68.0, le=98.0)
    ifa_compliance: float = Field(ge=0.0, le=1.0)
    dietary_score: float = Field(ge=0.0, le=1.0)
    prev_anemia: bool


class AssessmentResult(BaseModel):
    assessment_id: str
    timestamp: datetime
    mother_name: str
    risk: RiskResult
    anemia: Optional[AnemiaResult] = None
    referral: Optional[ReferralResult] = None
    alerts: list[str]
    follow_up_date: str
    recommendations: list[str]


class OutcomeRecord(BaseModel):
    """Record a birth outcome for Bayesian posterior updating."""
    age: int = Field(ge=12, le=55)
    parity: int = Field(ge=0, le=15)
    hemoglobin: float = Field(ge=3.0, le=20.0)
    bp_systolic: int = Field(ge=60, le=250)
    bp_diastolic: int = Field(ge=30, le=160)
    gestational_weeks: int = Field(ge=1, le=42)
    height_cm: float = Field(ge=100, le=220)
    weight_kg: float = Field(ge=25, le=200)
    complication_history: ComplicationHistory
    adverse_outcome: bool = Field(description="True if adverse maternal outcome occurred")


class HealthCheck(BaseModel):
    status: str
    version: str
    engines_loaded: dict[str, bool]
