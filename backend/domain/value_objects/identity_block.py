"""Identity block value object for canonical mapping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class IdentityBlock:
    """Represents a repeated identity section (policy, provider, patient)."""

    block_type: str  # policyHolderIdentity, providerIdentity, patientIdentity
    sequence: int
    present_fields: Sequence[str]
    policy_number: str | None = None
    policyholder_name: str | None = None
    policyholder_address: str | None = None
    provider_name: str | None = None
    provider_address: str | None = None
    patient_name: str | None = None
    patient_address: str | None = None
    birth_date: str | None = None
    type_of_bill: str | None = None
    fed_tax_no: str | None = None
    statement_period: str | None = None
    source_page: int | None = None
    source_field_ids: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """Serialize block for JSON output."""

        return {
            "blockType": self.block_type,
            "sequence": self.sequence,
            "presentFields": list(self.present_fields),
            "policyNumber": self.policy_number,
            "policyholderName": self.policyholder_name,
            "policyholderAddress": self.policyholder_address,
            "providerName": self.provider_name,
            "providerAddress": self.provider_address,
            "patientName": self.patient_name,
            "patientAddress": self.patient_address,
            "birthDate": self.birth_date,
            "typeOfBill": self.type_of_bill,
            "fedTaxNo": self.fed_tax_no,
            "statementPeriod": self.statement_period,
            "source": {
                "page": self.source_page,
                "fieldIds": list(self.source_field_ids),
            },
        }
