# FormSahayak End-to-End Testing Suite Summary

This document provides a comprehensive overview of the **End-to-End Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [e2e_test_cases.xlsx](file:///c:/formsahayakbackend/tests/e2e/e2e_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-E2E-001` through `TC-E2E-315`
- **Worksheet Tabs**: `E2E Test Cases`, `User Journeys`, `OCR to Form Guidance`, `Voice Assistance Flows`, `History & Feedback Loops`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`E2E Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`User Journeys`** | Focused testing category for User Journeys evaluation. | Test Scenario mapped to User Journeys |
| **`OCR to Form Guidance`** | Focused testing category for OCR to Form Guidance evaluation. | Test Scenario mapped to OCR to Form Guidance |
| **`Voice Assistance Flows`** | Focused testing category for Voice Assistance Flows evaluation. | Test Scenario mapped to Voice Assistance Flows |
| **`History & Feedback Loops`** | Focused testing category for History & Feedback Loops evaluation. | Test Scenario mapped to History & Feedback Loops |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_e2e_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_e2e_cases.py
```
This ensures complete auditability and ease of replication.
