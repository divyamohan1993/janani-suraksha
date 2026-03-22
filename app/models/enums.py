"""Enumerations for JananiSuraksha risk classification and facility capabilities."""
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CapabilityLevel(str, Enum):
    BASIC_EMOC = "basic_emoc"
    COMPREHENSIVE_EMOC = "comprehensive_emoc"
    BLOOD_TRANSFUSION = "blood_transfusion"
    C_SECTION = "c_section"
    NEONATAL_ICU = "neonatal_icu"

class FacilityType(str, Enum):
    SUB_CENTRE = "sub_centre"
    PHC = "phc"
    CHC = "chc"
    DISTRICT_HOSPITAL = "district_hospital"
    MEDICAL_COLLEGE = "medical_college"

class ComplicationHistory(str, Enum):
    NONE = "none"
    PREV_CSECTION = "prev_csection"
    PREV_PPH = "prev_pph"
    PREV_ECLAMPSIA = "prev_eclampsia"
    MULTIPLE = "multiple"

class InterventionUrgency(str, Enum):
    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"
    EMERGENCY = "emergency"

class BloodBankStatus(str, Enum):
    AVAILABLE = "available"
    LOW_STOCK = "low_stock"
    UNAVAILABLE = "unavailable"
