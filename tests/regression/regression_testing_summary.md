# FormSahayak Regression Testing Suite Summary

This document provides a comprehensive overview of the **Regression Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [regression_test_cases.xlsx](file:///c:/formsahayakbackend/tests/regression/regression_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-REG-001` through `TC-REG-315`
- **Worksheet Tabs**: `Regression Test Cases`, `Core Auth Regression`, `OCR Pipeline Regression`, `Guidance Engine Regression`, `Critical Path Suites`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`Regression Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`Core Auth Regression`** | Focused testing category for Core Auth Regression evaluation. | Test Scenario mapped to Core Auth Regression |
| **`OCR Pipeline Regression`** | Focused testing category for OCR Pipeline Regression evaluation. | Test Scenario mapped to OCR Pipeline Regression |
| **`Guidance Engine Regression`** | Focused testing category for Guidance Engine Regression evaluation. | Test Scenario mapped to Guidance Engine Regression |
| **`Critical Path Suites`** | Focused testing category for Critical Path Suites evaluation. | Test Scenario mapped to Critical Path Suites |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_regression_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_regression_cases.py
```
This ensures complete auditability and ease of replication.
