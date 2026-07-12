# FormSahayak System Testing Suite Summary

This document provides a comprehensive overview of the **System Testing** test cases designed for the **FormSahayak** project (Kotlin/Compose mobile client and FastAPI backend).

The complete list of styled test cases is saved in the Excel workbook [system_test_cases.xlsx](file:///c:/formsahayakbackend/tests/system/system_test_cases.xlsx).

---

## 📊 Suite Metrics & Distribution

- **Total Test Cases**: 315
- **Test Case IDs**: `TC-SYS-001` through `TC-SYS-315`
- **Worksheet Tabs**: `System Test Cases`, `File System & Storage`, `Network Latency & Failures`, `Resource CPU-RAM Limits`, `Concurrency & Locking`

### Sub-Sheet Layout Breakdown

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`System Test Cases`** | Master list containing all generated test cases for this category. | None (Master) |
| **`File System & Storage`** | Focused testing category for File System & Storage evaluation. | Test Scenario mapped to File System & Storage |
| **`Network Latency & Failures`** | Focused testing category for Network Latency & Failures evaluation. | Test Scenario mapped to Network Latency & Failures |
| **`Resource CPU-RAM Limits`** | Focused testing category for Resource CPU-RAM Limits evaluation. | Test Scenario mapped to Resource CPU-RAM Limits |
| **`Concurrency & Locking`** | Focused testing category for Concurrency & Locking evaluation. | Test Scenario mapped to Concurrency & Locking |

---

## 🔧 Automation & Scripting

The accompanying Python script `generate_system_cases.py` can be executed to rebuild the entire Excel sheet from clean source templates. 
To run the generator:
```powershell
python generate_system_cases.py
```
This ensures complete auditability and ease of replication.
