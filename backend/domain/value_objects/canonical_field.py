"""Canonical field metadata for Policy Conversion (60 benefit attributes)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Dict, Iterable, List, Tuple


class CanonicalGroup(str, Enum):
    """Single canonical group for policy conversion benefits."""

    POLICY_CONVERSION = "Policy Conversion (60 fields)"
    GENERAL_INVOICE = "General Invoice (deprecated)"
    CMR = "CMR (deprecated)"
    UB04 = "UB04 (deprecated)"


@dataclass(frozen=True)
class CanonicalField:
    """Metadata descriptor for a canonical field."""

    identifier: str
    label: str
    description: str
    group: CanonicalGroup
    order: int

    def key(self) -> str:
        return self.identifier


def _field(identifier: str, label: str, description: str, order: int) -> CanonicalField:
    return CanonicalField(
        identifier=identifier,
        label=label,
        description=description,
        group=CanonicalGroup.POLICY_CONVERSION,
        order=order,
    )


POLICY_CONVERSION_FIELDS: Tuple[CanonicalField, ...] = (
    _field("BENEFIT_TYPE", "Benefit Type", "Benefit category name", 1),
    _field("DAYS_OR_DOLLAR_BASED", "Days or Dollar Based", "Whether EP uses days", 2),
    _field("ELIMINATION_PERIOD", "Elimination Period", "Waiting days before benefits", 3),
    _field("EP_CALENDAR_OR_SERVICE_DAYS", "EP Calendar or Service Days", "Counts calendar or service days", 4),
    _field("EP_RENEWAL_OR_LIFETIME", "EP Renewal or Lifetime", "EP resets or lifetime", 5),
    _field("ELIM_PERIOD_EXEMPTIONS", "Elim Period Exemptions", "Services exempt from EP", 6),
    _field("MAXIMUM_BENEFIT_PERIOD", "Maximum Benefit Period", "Policy maximum limit", 7),
    _field("MAXIMUM_MONTHLY_LIMIT", "Maximum Monthly Limit", "Policy maximum limit", 8),
    _field("MAXIMUM_LIFETIME_BENEFIT", "Maximum Lifetime $Benefit", "Policy maximum limit", 9),
    _field("ADLS_REQUIRED", "ADL’s Required", "ADLs required for claim", 10),
    _field("AMBULATING", "Ambulating", "ADL ability status", 11),
    _field("BATHING", "Bathing", "ADL ability status", 12),
    _field("CONTINENCE", "Continence", "ADL ability status", 13),
    _field("DRESSING", "Dressing", "ADL ability status", 14),
    _field("EATING", "Eating", "ADL ability status", 15),
    _field("MEDICATIONS", "Medications", "ADL ability status", 16),
    _field("TOILETING", "Toileting", "Field info short answer", 17),
    _field("TRANSFERRING", "Transferring", "Field info short answer", 18),
    _field("CARE_COORDINATION", "Care Coordination", "Field info short answer", 19),
    _field("NURSING_HOME", "Nursing Home", "Field info short answer", 20),
    _field("NH_ALF_BED_RESERVATION_AMOUNT", "NH/ALF Bed Reservation Amount", "Field info short answer", 21),
    _field("NH_ALF_BED_RESERVATION_DAYS", "NH/ALF Bed Reservation Days", "Field info short answer", 22),
    _field("ASSISTED_LIVING", "Assisted Living", "Field info short answer", 23),
    _field("HOME_HEALTH_CARE", "Home Health Care", "Field info short answer", 24),
    _field("HHC_BED_RESERVATION_AMOUNT", "HHC Bed Reservation Amount", "Field info short answer", 25),
    _field("HHC_BED_RESERVATION_DAYS", "HHC Bed Reservation Days", "Field info short answer", 26),
    _field("ADULT_DAY_CARE", "Adult Day Care", "Field info short answer", 27),
    _field("ALTERNATIVE_PLAN_OF_CARE", "Alternative Plan of Care", "Field info short answer", 28),
    _field("CAREGIVER_TRAINING", "Caregiver Training", "Field info short answer", 29),
    _field("DURABLE_MEDICAL_EQUIPMENT", "Durable Medical Equipment (DME)", "Field info short answer", 30),
    _field("EMERGENCY_MEDICAL_SYSTEM_DEVICES", "Emergency Medical System/Devices", "Field info short answer", 31),
    _field("HOME_MODIFICATIONS", "Home Modifications", "Field info short answer", 32),
    _field("HOMEMAKER_SERVICES", "Homemaker Services", "Field info short answer", 33),
    _field("HOSPICE_AMOUNT", "Hospice Amount", "Field info short answer", 34),
    _field("HOSPICE_DAYS", "Hospice Days", "Field info short answer", 35),
    _field("PERSONAL_CARE_ADVISOR", "Personal Care Advisor", "Field info short answer", 36),
    _field("PERSONAL_CARE_SERVICES", "Personal Care Services", "Field info short answer", 37),
    _field("PRESCRIPTION_DRUGS", "Prescription Drugs", "Field info short answer", 38),
    _field("RESPITE_AMOUNT", "Respite Amount", "Field info short answer", 39),
    _field("RESPITE_DAYS", "Respite Days", "Field info short answer", 40),
    _field("THERAPEUTIC_EQUIPMENT_RENTAL", "Therapeutic Equipment Rental", "Field info short answer", 41),
    _field("NONFORFEITURE_BENEFIT", "Nonforfeiture Benefit", "Field info short answer", 42),
    _field("PREMIUM_PAYMENT_OPTIONS", "Premium Payment Options", "Field info short answer", 43),
    _field("RESTORATION_OF_BENEFITS", "Restoration of Benefits", "Field info short answer", 44),
    _field("RETURN_REFUND_OF_PREMIUM", "Return/Refund of Premium", "Premium refund rule", 45),
    _field("SIMPLE_INFLATION", "Simple Inflation", "Inflation protection type", 46),
    _field("COMPOUND_INFLATION", "Compound Inflation", "Inflation protection type", 47),
    _field("EXTENSION_OF_BENEFITS", "Extension of Benefits", "Field info short answer", 48),
    _field("WAIVER_OF_PREMIUM", "Waiver of Premium", "Premium waived on claim", 49),
    _field("SURVIVORSHIP", "Survivorship", "Benefit for surviving insured", 50),
    _field("GUARANTEED_PURCHASE_OPTION", "Guaranteed Purchase Option", "Option to increase coverage", 51),
    _field("INDEMNITY_BENEFIT", "Indemnity Benefit", "Pays fixed amount", 52),
    _field("SUBSTANTIAL_ASSISTANCE", "Substantial Assistance", "Care assistance level", 53),
    _field("STANDBY_ASSISTANCE", "Standby Assistance", "Care assistance level", 54),
    _field("SUBSTANTIAL_SUPERVISION", "Substantial Supervision", "Supervision need level", 55),
    _field("PREMIUM_REFUND_AT_DEATH", "Premium Refund at Death", "Premium refund rule", 56),
    _field("RENEWAL_PREMIUM", "Renewal Premium", "Field info short answer", 57),
    _field("CANCELLATION", "Cancellation", "Policy cancellation terms", 58),
    _field("ADDITIONAL_BENEFITS_1", "Additional Benefits: (Enter Benefit Description Here)", "Extra benefit description", 59),
    _field("ADDITIONAL_BENEFITS_2", "Additional Benefits: (Enter Benefit Description Here)", "Extra benefit description", 60),
)

ALL_CANONICAL_FIELDS: Tuple[CanonicalField, ...] = POLICY_CONVERSION_FIELDS


class CanonicalFieldIndex:
    """Convenience accessors for canonical field collections."""

    _by_identifier: ClassVar[Dict[str, CanonicalField]] = {
        field.identifier: field for field in ALL_CANONICAL_FIELDS
    }
    _by_label: ClassVar[Dict[str, CanonicalField]] = {
        field.label: field for field in ALL_CANONICAL_FIELDS
    }

    @classmethod
    def by_identifier(cls, identifier: str) -> CanonicalField:
        return cls._by_identifier[identifier]

    @classmethod
    def by_label(cls, label: str) -> CanonicalField:
        return cls._by_label[label]

    @classmethod
    def all(cls) -> Tuple[CanonicalField, ...]:
        return ALL_CANONICAL_FIELDS

    @classmethod
    def ordered_labels(cls) -> List[str]:
        return [field.label for field in sorted(ALL_CANONICAL_FIELDS, key=lambda f: f.order)]

    @classmethod
    def ordered(cls) -> Tuple[CanonicalField, ...]:
        return tuple(sorted(ALL_CANONICAL_FIELDS, key=lambda f: f.order))

    @classmethod
    def names(cls) -> Tuple[str, ...]:
        return tuple(field.identifier for field in cls.ordered())

    @classmethod
    def for_group(cls, group: CanonicalGroup) -> Tuple[CanonicalField, ...]:
        if group is CanonicalGroup.POLICY_CONVERSION:
            return cls.ordered()
        return tuple()

    @classmethod
    def identity_block_fields(cls) -> Tuple[CanonicalField, ...]:
        return tuple()


def canonical_field_labels(group: CanonicalGroup | None = None) -> List[str]:
    """Return ordered labels; group param kept for backward compatibility."""
    if group and group is not CanonicalGroup.POLICY_CONVERSION:
        return []
    return CanonicalFieldIndex.ordered_labels()
