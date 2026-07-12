# FormSahayak Integration Testing Suite Summary

This document provides a comprehensive overview of the **Integration Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [integration_test_cases.xlsx](file:///c:/formsahayakbackend/tests/integration/integration_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-INT-001` through `TC-INT-315`
- **Worksheet Tabs**: `Integration Test Cases`, `Mobile-API Integration`, `API-Database Integration`, `OCR Service Integration`, `Groq-LLM Integration`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`Integration Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`Mobile-API Integration`** | Focused testing category for Mobile-API Integration evaluation. | Test Scenario mapped to Mobile-API Integration |
| **`API-Database Integration`** | Focused testing category for API-Database Integration evaluation. | Test Scenario mapped to API-Database Integration |
| **`OCR Service Integration`** | Focused testing category for OCR Service Integration evaluation. | Test Scenario mapped to OCR Service Integration |
| **`Groq-LLM Integration`** | Focused testing category for Groq-LLM Integration evaluation. | Test Scenario mapped to Groq-LLM Integration |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_integration_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_integration_cases.py
```
This ensures complete auditability and ease of replication.
