# FormSahayak User Acceptance Testing (UAT) Suite Summary

This document provides a comprehensive overview of the **User Acceptance Testing (UAT)** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [uat_test_cases.xlsx](file:///c:/formsahayakbackend/tests/uat/uat_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-UAT-001` through `TC-UAT-315`
- **Worksheet Tabs**: `UAT Test Cases`, `First-time User Flow`, `Form Guidance Clarity`, `Voice Helper Usability`, `Error Guidance Feedback`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`UAT Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`First-time User Flow`** | Focused testing category for First-time User Flow evaluation. | Test Scenario mapped to First-time User Flow |
| **`Form Guidance Clarity`** | Focused testing category for Form Guidance Clarity evaluation. | Test Scenario mapped to Form Guidance Clarity |
| **`Voice Helper Usability`** | Focused testing category for Voice Helper Usability evaluation. | Test Scenario mapped to Voice Helper Usability |
| **`Error Guidance Feedback`** | Focused testing category for Error Guidance Feedback evaluation. | Test Scenario mapped to Error Guidance Feedback |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_uat_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_uat_cases.py
```
This ensures complete auditability and ease of replication.
