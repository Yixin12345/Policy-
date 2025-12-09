# Consolidated Field Mapping Specification

## General Invoice (Fields 1–18)

1. **Policy number**  
   Unique LTC policy identifier (alphanumeric; matches insurer records).

2. **Policyholder name**  
   Full legal name of the policyholder.

3. **Policyholder address**  
   Complete mailing address (street, city, state, ZIP).

4. **Provider name**  
   Official name of the billing facility or service organization.

5. **Provider address**  
   Facility/provider mailing address (street, city, state, ZIP).

6. **Invoice number**  
   Provider-issued billing or statement identifier.

7. **Invoice date / statement date**  
   Date the invoice/statement was issued.

8. **Tax ID**  
   Provider FEIN (often also present on UB04 forms).

9. **Total amount**  
   Gross charges before credits or adjustments.

### Invoice Line Items (Fields 10–18)

Each invoice contains zero or more line items. Every line item should capture:

- **Description / activity** (Field 10): Narrative or coded description (rent, therapy, services, fees, etc.).
- **Start date** (Field 11): First service date in the billing period for this entry.
- **End date** (Field 12): Last service date in the billing period for this entry.
- **Unit type** (Field 13): Billing unit basis (days, hours, sessions, monthly rent, etc.).
- **Unit / quantity** (Field 14): Number of units billed for the line item.
- **Charges / amount** (Field 15): Charge per service or unit before credits.
- **Balance** (Field 16): Remaining unpaid amount after payments/credits for the line item.
- **Total due / balance due** (Field 17): Final payable amount due for the entry.
- **Credits** (Field 18): Payments, discounts, or adjustments reducing this line item.

---

## Continued Monthly Residence (CMR) Form (Fields 21–34)

21. **Policy number**  
    LTC policy identifier tied to the resident.

22. **Policyholder name**  
    Insured resident’s full legal name.

23. **Policyholder address**  
    Resident mailing address (street, city, state, ZIP).

24. **Provider name**  
    Residential facility name.

25. **Provider address**  
    Facility mailing address (street, city, state, ZIP).

26. **Month of service from**  
    First month/year of the documented service period.

27. **Month of service through**  
    Last month/year of the documented service period.

28. **Select the level of care**  
    Facility-selected care category (assisted living, nursing, memory care, etc.).

29. **Yes / no (absence question)**  
    Response indicating whether the resident was absent during the period.

30. **Absence details (if yes)**  
    Departure date, return date, reason, admission date, discharge date (composite block).

31. **Policy number (duplicate block)**  
    Repeated policy identifier for verification.

32. **Policyholder name (duplicate block)**  
    Repeated policyholder name.

33. **Policyholder address (duplicate block)**  
    Repeated policyholder address.

34. **Provider name (duplicate block)**  
    Repeated facility/provider name.

---

## UB04 Form (Fields 35–56)

35. **Provider name (Box 1/2)**  
    Billing provider’s legal name.

36. **Provider address (Box 1/2)**  
    Provider address (street, city, state, ZIP).

37. **Type of bill (Box 4)**  
    Three-digit code (facility, classification, frequency).

38. **Fed tax no (Box 5)**  
    Provider EIN/TIN.

39. **Statement period / service dates (Box 6)**  
    Start and end service period dates.

40. **Patient name (Box 8)**  
    Patient legal name (Last, First, MI).

41. **Patient address (Box 9)**  
    Patient address (street, city, state, ZIP).

42. **Birth date (Box 10)**  
    Patient DOB (MMDDYYYY).

43. **Medicare/Medicaid number (Box 38)**  
     Medicare or Medicaid beneficiary identification number, used for payer claim processing.

44. **Line items (Boxes 42–47)**  
    Itemized services: revenue code, description, procedure code, service date, units, total charge.

45. **Total**  
    Sum of all billed charges pre-adjustment.

46. **Payer name(s) (Box 50)**  
    Ordered payer list (primary → secondary).

47. **AOB on file (Box 53)**  
    Assignment of Benefits indicator (Y/N).

48. **Estimated amount due (Box 55)**  
    Estimated patient/secondary responsibility amount.

49. **Provider name (duplicate, Box 1/2)**  
    Repeated provider name block.

50. **Provider address (duplicate, Box 1/2)**  
    Repeated provider address block.

51. **Type of bill (duplicate, Box 4)**  
    Repeated bill-type code.

52. **Fed tax no (duplicate, Box 5)**  
    Repeated EIN/TIN.

53. **Statement period / service dates (duplicate, Box 6)**  
    Repeated service period dates.

54. **Patient name (duplicate, Box 8)**  
    Repeated patient name.

55. **Patient address (duplicate, Box 9)**  
    Repeated patient address.

56. **Birth date (duplicate, Box 10)**  
    Patient DOB (MMDDYYYY) repeated.

57. **Medicare and Medicaid (duplicate, Box 38)**
    Medicare or Medicaid beneficiary identification number, used for payer claim processing.
---