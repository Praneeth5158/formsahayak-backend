# FormSahayak API Testing Suite Summary

This document provides a comprehensive overview of the **API Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [api_test_cases.xlsx](file:///c:/formsahayakbackend/tests/api/api_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-API-001` through `TC-API-315`
- **Worksheet Tabs**: `API Test Cases`, `Authentication Endpoints`, `Document & OCR Routes`, `Voice & History Services`, `Error Payloads & Validation`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`API Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`Authentication Endpoints`** | Focused testing category for Authentication Endpoints evaluation. | Test Scenario mapped to Authentication Endpoints |
| **`Document & OCR Routes`** | Focused testing category for Document & OCR Routes evaluation. | Test Scenario mapped to Document & OCR Routes |
| **`Voice & History Services`** | Focused testing category for Voice & History Services evaluation. | Test Scenario mapped to Voice & History Services |
| **`Error Payloads & Validation`** | Focused testing category for Error Payloads & Validation evaluation. | Test Scenario mapped to Error Payloads & Validation |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_api_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_api_cases.py
```
This ensures complete auditability and ease of replication.
