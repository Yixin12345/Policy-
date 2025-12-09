"""Canonical field metadata definitions.

This module enumerates the canonical field labels defined in
`RequiredFields.md` and associates them with stable identifiers,
category groupings, and ordering indices. The display labels must
match the specification exactly (case, spacing, punctuation) to
ensure downstream UI parity.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Dict, Iterable, List, Tuple


class CanonicalGroup(str, Enum):
    """Logical sections mirroring the RequiredFields specification."""

    GENERAL_INVOICE = "General Invoice (Fields 1–18)"
    CMR = "Continued Monthly Residence (CMR) Form (Fields 21–34)"
    UB04 = "UB04 Form (Fields 35–56)"


@dataclass(frozen=True)
class CanonicalField:
    """Metadata descriptor for a canonical field."""

    identifier: str
    label: str
    description: str
    group: CanonicalGroup
    order: int
    is_identity_block_member: bool = False
    include_in_group: bool = True
    line_item_attribute: str | None = None

    def key(self) -> str:
        """Stable key for dictionary lookups (identifier alias)."""

        return self.identifier


def _field(
    identifier: str,
    label: str,
    group: CanonicalGroup,
    order: int,
    description: str,
    *,
    identity_member: bool = False,
    include_in_group: bool = True,
    line_item_attribute: str | None = None,
) -> CanonicalField:
    return CanonicalField(
        identifier=identifier,
        label=label,
        description=description,
        group=group,
        order=order,
        is_identity_block_member=identity_member,
        include_in_group=include_in_group,
        line_item_attribute=line_item_attribute,
    )


GENERAL_INVOICE_CORE_FIELDS: Tuple[CanonicalField, ...] = (
    _field("POLICY_NUMBER", "Policy number", CanonicalGroup.GENERAL_INVOICE, 1,
           "Unique LTC policy identifier (alphanumeric; matches insurer records)."),
    _field("POLICYHOLDER_NAME", "Policyholder name", CanonicalGroup.GENERAL_INVOICE, 2,
           "Full legal name of the policyholder."),
    _field(
        "POLICYHOLDER_ADDRESS",
        "Policyholder address",
        CanonicalGroup.GENERAL_INVOICE,
        3,
        "Complete mailing address (street, city, state, ZIP).",
    ),
    _field("PROVIDER_NAME", "Provider name", CanonicalGroup.GENERAL_INVOICE, 4,
           "Official name of the billing facility or service organization."),
    _field("PROVIDER_ADDRESS", "Provider address", CanonicalGroup.GENERAL_INVOICE, 5,
           "Facility/provider mailing address (street, city, state, ZIP)."),
    _field("INVOICE_NUMBER", "Invoice number", CanonicalGroup.GENERAL_INVOICE, 6,
           "Provider-issued billing or statement identifier."),
    _field(
        "INVOICE_DATE_STATEMENT_DATE",
        "Invoice date / statement date",
        CanonicalGroup.GENERAL_INVOICE,
        7,
        "Date the invoice/statement was issued.",
    ),
    _field("TAX_ID", "Tax ID", CanonicalGroup.GENERAL_INVOICE, 8,
           "Provider FEIN (often also present on UB04 forms)."),
    _field("TOTAL_AMOUNT", "Total amount", CanonicalGroup.GENERAL_INVOICE, 9,
           "Gross charges before credits or adjustments."),
)

GENERAL_INVOICE_LINE_ITEM_FIELDS: Tuple[CanonicalField, ...] = (
    _field(
        "DESCRIPTION_ACTIVITY",
        "Description / activity",
        CanonicalGroup.GENERAL_INVOICE,
        10,
        "Invoice line item description (Field 10).",
        include_in_group=False,
        line_item_attribute="description",
    ),
    _field(
        "START_DATE",
        "Start date",
        CanonicalGroup.GENERAL_INVOICE,
        11,
        "Line item service start date (Field 11).",
        include_in_group=False,
        line_item_attribute="startDate",
    ),
    _field(
        "END_DATE",
        "End date",
        CanonicalGroup.GENERAL_INVOICE,
        12,
        "Line item service end date (Field 12).",
        include_in_group=False,
        line_item_attribute="endDate",
    ),
    _field(
        "UNIT_TYPE",
        "Unit type",
        CanonicalGroup.GENERAL_INVOICE,
        13,
        "Line item billing unit type (Field 13).",
        include_in_group=False,
        line_item_attribute="unitType",
    ),
    _field(
        "UNIT_QUANTITY",
        "Unit / quantity",
        CanonicalGroup.GENERAL_INVOICE,
        14,
        "Line item quantity (Field 14).",
        include_in_group=False,
        line_item_attribute="unitQuantity",
    ),
    _field(
        "CHARGES_AMOUNT",
        "Charges / amount",
        CanonicalGroup.GENERAL_INVOICE,
        15,
        "Line item charge amount (Field 15).",
        include_in_group=False,
        line_item_attribute="chargesAmount",
    ),
    _field(
        "BALANCE",
        "Balance",
        CanonicalGroup.GENERAL_INVOICE,
        16,
        "Line item remaining balance (Field 16).",
        include_in_group=False,
        line_item_attribute="balance",
    ),
    _field(
        "TOTAL_DUE_BALANCE_DUE",
        "Total due / balance due",
        CanonicalGroup.GENERAL_INVOICE,
        17,
        "Line item total due (Field 17).",
        include_in_group=False,
        line_item_attribute="totalDue",
    ),
    _field(
        "CREDITS",
        "Credits",
        CanonicalGroup.GENERAL_INVOICE,
        18,
        "Line item credits or adjustments (Field 18).",
        include_in_group=False,
        line_item_attribute="credits",
    ),
)

GENERAL_INVOICE_FIELDS: Tuple[CanonicalField, ...] = (
    *GENERAL_INVOICE_CORE_FIELDS,
    *GENERAL_INVOICE_LINE_ITEM_FIELDS,
)

UB04_LINE_ITEM_ATTRIBUTES: Tuple[Tuple[str, str], ...] = (
    ("revenueCode", "Revenue code"),
    ("description", "Description"),
    ("procedureCode", "Procedure code"),
    ("procedureModifier", "Procedure modifier"),
    ("serviceDate", "Service date"),
    ("serviceDateFrom", "Service date (from)"),
    ("serviceDateTo", "Service date (to)"),
    ("units", "Units"),
    ("rate", "Rate"),
    ("totalCharge", "Total charge"),
)

CMR_FIELDS: Tuple[CanonicalField, ...] = (
    _field("CMR_POLICY_NUMBER", "Policy number", CanonicalGroup.CMR, 21,
           "LTC policy identifier tied to the resident."),
    _field("CMR_POLICYHOLDER_NAME", "Policyholder name", CanonicalGroup.CMR, 22,
           "Insured resident's full legal name."),
    _field(
        "CMR_POLICYHOLDER_ADDRESS",
        "Policyholder address",
        CanonicalGroup.CMR,
        23,
        "Resident mailing address (street, city, state, ZIP).",
    ),
    _field("CMR_PROVIDER_NAME", "Provider name", CanonicalGroup.CMR, 24,
           "Residential facility name."),
    _field(
        "CMR_PROVIDER_ADDRESS",
        "Provider address",
        CanonicalGroup.CMR,
        25,
        "Facility mailing address (street, city, state, ZIP).",
    ),
    _field(
        "MONTH_OF_SERVICE_FROM",
        "Month of service from",
        CanonicalGroup.CMR,
        26,
        "First month/year of the documented service period.",
    ),
    _field(
        "MONTH_OF_SERVICE_THROUGH",
        "Month of service through",
        CanonicalGroup.CMR,
        27,
        "Last month/year of the documented service period.",
    ),
    _field(
        "SELECT_THE_LEVEL_OF_CARE",
        "Select the level of care",
        CanonicalGroup.CMR,
        28,
        "Facility-selected care category (assisted living, nursing, memory care, etc.).",
    ),
    _field(
        "ABSENCE_QUESTION",
        "Yes / no (absence question)",
        CanonicalGroup.CMR,
        29,
        "Response indicating whether the resident was absent during the period.",
    ),
    _field(
        "ABSENCE_DETAILS",
        "Absence details (if yes)",
        CanonicalGroup.CMR,
        30,
        "Departure date, return date, reason, admission date, discharge date (composite block).",
    ),
    _field(
        "CMR_POLICY_NUMBER_DUPLICATE",
        "Policy number (duplicate block)",
        CanonicalGroup.CMR,
        31,
        "Repeated policy identifier for verification.",
        identity_member=True,
    ),
    _field(
        "CMR_POLICYHOLDER_NAME_DUPLICATE",
        "Policyholder name (duplicate block)",
        CanonicalGroup.CMR,
        32,
        "Repeated policyholder name.",
        identity_member=True,
    ),
    _field(
        "CMR_POLICYHOLDER_ADDRESS_DUPLICATE",
        "Policyholder address (duplicate block)",
        CanonicalGroup.CMR,
        33,
        "Repeated policyholder address.",
        identity_member=True,
    ),
    _field(
        "CMR_PROVIDER_NAME_DUPLICATE",
        "Provider name (duplicate block)",
        CanonicalGroup.CMR,
        34,
        "Repeated facility/provider name.",
        identity_member=True,
    ),
)

UB04_FIELDS: Tuple[CanonicalField, ...] = (
    _field(
        "UB04_PROVIDER_NAME",
        "Provider name (Box 1/2)",
        CanonicalGroup.UB04,
        35,
        "Billing provider's legal name.",
    ),
    _field(
        "UB04_PROVIDER_ADDRESS",
        "Provider address (Box 1/2)",
        CanonicalGroup.UB04,
        36,
        "Provider address (street, city, state, ZIP).",
    ),
    _field("TYPE_OF_BILL", "Type of bill (Box 4)", CanonicalGroup.UB04, 37,
           "Three-digit code (facility, classification, frequency)."),
    _field("FED_TAX_NO", "Fed tax no (Box 5)", CanonicalGroup.UB04, 38,
           "Provider EIN/TIN."),
    _field(
        "STATEMENT_PERIOD",
        "Statement period / service dates (Box 6)",
        CanonicalGroup.UB04,
        39,
        "Start and end service period dates.",
    ),
    _field("PATIENT_NAME", "Patient name (Box 8)", CanonicalGroup.UB04, 40,
           "Patient legal name (Last, First, MI)."),
    _field(
        "PATIENT_ADDRESS",
        "Patient address (Box 9)",
        CanonicalGroup.UB04,
        41,
        "Patient address (street, city, state, ZIP).",
    ),
    _field("BIRTH_DATE", "Birth date (Box 10)", CanonicalGroup.UB04, 42,
           "Patient DOB (MMDDYYYY)."),
    _field(
        "MEDICARE_MEDICAID_NUMBER",
        "Medicare/Medicaid number (Box 38)",
        CanonicalGroup.UB04,
        43,
        "Beneficiary identification number.",
    ),
    _field(
        "LINE_ITEMS",
        "Line items (Boxes 42–47)",
        CanonicalGroup.UB04,
        44,
        "Itemized services: revenue code, description, procedure code, service date, units, total charge.",
        include_in_group=False,
    ),
    _field("TOTAL", "Total", CanonicalGroup.UB04, 45,
           "Sum of all billed charges pre-adjustment."),
    _field(
        "PAYER_NAMES",
        "Payer name(s) (Box 50)",
        CanonicalGroup.UB04,
        46,
        "Ordered payer list (primary -> secondary).",
    ),
    _field(
        "AOB_ON_FILE",
        "AOB on file (Box 53)",
        CanonicalGroup.UB04,
        47,
        "Assignment of Benefits indicator (Y/N).",
    ),
    _field(
        "ESTIMATED_AMOUNT_DUE",
        "Estimated amount due (Box 55)",
        CanonicalGroup.UB04,
        48,
        "Estimated patient/secondary responsibility amount.",
    ),
    _field(
        "UB04_PROVIDER_NAME_DUPLICATE",
        "Provider name (duplicate, Box 1/2)",
        CanonicalGroup.UB04,
        49,
        "Repeated provider name block.",
        identity_member=True,
    ),
    _field(
        "UB04_PROVIDER_ADDRESS_DUPLICATE",
        "Provider address (duplicate, Box 1/2)",
        CanonicalGroup.UB04,
        50,
        "Repeated provider address block.",
        identity_member=True,
    ),
    _field(
        "TYPE_OF_BILL_DUPLICATE",
        "Type of bill (duplicate, Box 4)",
        CanonicalGroup.UB04,
        51,
        "Repeated bill-type code.",
        identity_member=True,
    ),
    _field(
        "FED_TAX_NO_DUPLICATE",
        "Fed tax no (duplicate, Box 5)",
        CanonicalGroup.UB04,
        52,
        "Repeated EIN/TIN.",
        identity_member=True,
    ),
    _field(
        "STATEMENT_PERIOD_DUPLICATE",
        "Statement period / service dates (duplicate, Box 6)",
        CanonicalGroup.UB04,
        53,
        "Repeated service period dates.",
        identity_member=True,
    ),
    _field(
        "PATIENT_NAME_DUPLICATE",
        "Patient name (duplicate, Box 8)",
        CanonicalGroup.UB04,
        54,
        "Repeated patient name.",
        identity_member=True,
    ),
    _field(
        "PATIENT_ADDRESS_DUPLICATE",
        "Patient address (duplicate, Box 9)",
        CanonicalGroup.UB04,
        55,
        "Repeated patient address.",
        identity_member=True,
    ),
    _field(
        "BIRTH_DATE_DUPLICATE",
        "Birth date (duplicate, Box 10)",
        CanonicalGroup.UB04,
        56,
        "Patient DOB (MMDDYYYY) repeated.",
        identity_member=True,
    ),
)


ALL_CANONICAL_FIELDS: Tuple[CanonicalField, ...] = (
    *GENERAL_INVOICE_FIELDS,
    *CMR_FIELDS,
    *UB04_FIELDS,
)


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
    def for_group(cls, group: CanonicalGroup) -> Tuple[CanonicalField, ...]:
        return tuple(field for field in ALL_CANONICAL_FIELDS if field.group is group)

    @classmethod
    def identity_block_fields(cls) -> Tuple[CanonicalField, ...]:
        return tuple(
            field for field in ALL_CANONICAL_FIELDS if field.is_identity_block_member
        )

    @classmethod
    def ordered_labels(cls) -> List[str]:
        return [field.label for field in sorted(ALL_CANONICAL_FIELDS, key=lambda f: f.order)]


def canonical_field_labels(group: CanonicalGroup | None = None) -> List[str]:
    """Return ordered labels, optionally filtered by group."""

    fields: Iterable[CanonicalField]
    if group is None:
        fields = ALL_CANONICAL_FIELDS
    else:
        fields = (field for field in ALL_CANONICAL_FIELDS if field.group is group)

    return [field.label for field in sorted(fields, key=lambda f: f.order)]


__all__ = [
    "CanonicalField",
    "CanonicalGroup",
    "CanonicalFieldIndex",
    "GENERAL_INVOICE_CORE_FIELDS",
    "GENERAL_INVOICE_LINE_ITEM_FIELDS",
    "GENERAL_INVOICE_FIELDS",
    "UB04_LINE_ITEM_ATTRIBUTES",
    "CMR_FIELDS",
    "UB04_FIELDS",
    "ALL_CANONICAL_FIELDS",
    "canonical_field_labels",
]
