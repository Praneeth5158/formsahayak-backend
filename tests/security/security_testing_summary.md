# FormSahayak Security Testing Suite Summary

This document provides a comprehensive overview of the **Security Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [security_test_cases.xlsx](file:///c:/formsahayakbackend/tests/security/security_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-SEC-001` through `TC-SEC-315`
- **Worksheet Tabs**: `Security Test Cases`, `Auth & Session Security`, `Data Encryption & Privacy`, `Injection & XSS Protections`, `API Rate Limiting`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`Security Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`Auth & Session Security`** | Focused testing category for Auth & Session Security evaluation. | Test Scenario mapped to Auth & Session Security |
| **`Data Encryption & Privacy`** | Focused testing category for Data Encryption & Privacy evaluation. | Test Scenario mapped to Data Encryption & Privacy |
| **`Injection & XSS Protections`** | Focused testing category for Injection & XSS Protections evaluation. | Test Scenario mapped to Injection & XSS Protections |
| **`API Rate Limiting`** | Focused testing category for API Rate Limiting evaluation. | Test Scenario mapped to API Rate Limiting |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_security_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_security_cases.py
```
This ensures complete auditability and ease of replication.
