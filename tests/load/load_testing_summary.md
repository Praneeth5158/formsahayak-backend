# FormSahayak Load Testing Suite Summary

This document provides a comprehensive overview of the load testing suite designed for **FormSahayak** (FastAPI backend and Kotlin mobile client). The load testing plan targets resource limitations, latency ceilings, concurrency bottlenecks, scaling triggers, database lock contention, and socket pooling limits under load.

The complete list of formatted load test cases is saved in the Excel workbook [load_test_cases.xlsx](file:///c:/formsahayakbackend/load_test_cases.xlsx).

---

## 📊 Load Suite Metrics & Distribution

- **Total Test Cases**: 312
- **Test Case IDs**: `TS-LOAD-001` through `TS-LOAD-312`
- **Total Modules Covered**: 13
- **Test Cases per Module**: Exactly 24 unique load test cases each

### Distribution by Load Test Type
The load tests are categorized into four specialized profiles:
1. **Load Test**: Evaluates normal, step-up, and expected peak operational loads (6 cases per module, 78 cases total).
2. **Stress Test**: Determines database connection saturation limits, memory heap ceilings, file descriptor caps, and CPU overload constraints (6 cases per module, 78 cases total).
3. **Spike Test**: Validates auto-scaling reaction speed, rate limiting triggers, and rapid load surge recovery (6 cases per module, 78 cases total).
4. **Endurance Test**: Checks long-term stability, memory leaks, log file exhaustion, and socket re-use limits under persistent load (6 cases per module, 78 cases total).

---

## 📂 Excel Workbook Structure

The generated Excel workbook [load_test_cases.xlsx](file:///c:/formsahayakbackend/load_test_cases.xlsx) contains five sheets structured for analysis:

| Sheet Name | Description | Filter Criteria |
| :--- | :--- | :--- |
| **`Load Test Cases`** | Master list of all 312 load testing cases. | None (Master Sheet) |
| **`Stress Tests`** | Test cases focused on system limits and breaking points. | `Load Scenario contains 'Stress'` |
| **`Spike Tests`** | Test cases evaluating sudden traffic surges and auto-scaling. | `Load Scenario contains 'Spike'` |
| **`Endurance Tests`** | Test cases focused on long-term stability and soak runs. | `Load Scenario contains 'Endurance' or 'Soak'` |
| **`Performance Summary`** | KPI Dashboard outlining targets, SLA thresholds, and capacities. | Custom Dashboard Layout |

### Column Layout (Sheets 1-4)
Every sheet contains the following exact columns:
1. **`Test Case ID`**: Unique identifier (`TS-LOAD-XXX`).
2. **`Module`**: System module under load.
3. **`Load Scenario`**: Specific load profile details.
4. **`Concurrent Users`**: Mock concurrent client connections (50 up to 5000).
5. **`Request Count`**: Total simulated queries sent (1000 up to 1,000,000).
6. **`Duration`**: Length of the load window (1 min up to 24 hours).
7. **`Expected Result`**: Graceful failure limits, success expectations, or error behaviors.
8. **`Threshold`**: Targeting response times (e.g. `<= 200ms`) and maximum error rates.
9. **`Priority`**: Business value rank (`Critical`, `High`, `Medium`, `Low`).
10. **`Severity`**: Impact rank (`Critical`, `Major`, `Medium`, `Minor`).

---

## 🏎️ Performance Targets & SLA Thresholds

Our base SLA thresholds are customized by module complexity and scale up dynamically based on concurrency levels:

| System Module | Base SLA Latency | Target Concurrency | Core Load Testing Scope |
| :--- | :--- | :--- | :--- |
| **Database connection** | `<= 150ms` | 500 users | SQLAlchemy connection pooling and Aiven MySQL limits |
| **API routing** | `<= 200ms` | 100 users | FastAPI core endpoints path parameter parsing |
| **Login API** | `<= 250ms` | 50 users | Token generation, validation, and database lookup |
| **Feedback Submission** | `<= 300ms` | 50 users | Write operations, feedback commits, transaction scopes |
| **Registration API** | `<= 400ms` | 50 users | Password hashing (bcrypt) and write constraints checking |
| **Admin Stats API** | `<= 600ms` | 120 users | heavy aggregation query indexing and query optimization |
| **Form Upload API** | `<= 1200ms` | 200 users | File stream uploads and temporary file buffers writing |
| **OCR Image Pipeline** | `<= 3000ms` | 200 users | EasyOCR image text extraction bounding box mapping |
