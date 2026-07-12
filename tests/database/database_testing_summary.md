# FormSahayak Database Testing Suite Summary

This document provides a comprehensive overview of the **Database Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [database_test_cases.xlsx](file:///c:/formsahayakbackend/tests/database/database_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-DB-001` through `TC-DB-315`
- **Worksheet Tabs**: `Database Test Cases`, `Schema Constraints`, `Transaction Rollbacks`, `Indexing & Query Performance`, `MySQL Lock Contention`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`Database Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`Schema Constraints`** | Focused testing category for Schema Constraints evaluation. | Test Scenario mapped to Schema Constraints |
| **`Transaction Rollbacks`** | Focused testing category for Transaction Rollbacks evaluation. | Test Scenario mapped to Transaction Rollbacks |
| **`Indexing & Query Performance`** | Focused testing category for Indexing & Query Performance evaluation. | Test Scenario mapped to Indexing & Query Performance |
| **`MySQL Lock Contention`** | Focused testing category for MySQL Lock Contention evaluation. | Test Scenario mapped to MySQL Lock Contention |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_database_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_database_cases.py
```
This ensures complete auditability and ease of replication.
