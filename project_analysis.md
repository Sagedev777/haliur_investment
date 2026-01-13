# Haliur Investment Project Analysis

## 1. Executive Summary
Haliur Investment is a comprehensive **Microfinance / Investment Management System** built with **Django**. It is designed to manage client accounts, savings, and complex loan lifecycles with strict role-based access control. The system enforces a "savings-first" lending model where loan eligibility is tied to accumulated savings.

## 2. Technology Stack
-   **Framework**: Django 4.2.7 (Python)
-   **Database**: PostgreSQL (`haliqur_investments`)
-   **Dependencies**:
    -   `psycopg` (Database adapter)
    -   `openpyxl` (Excel processing, likely for reports/bulk ops)
    -   `reportlab` (PDF generation)
    -   `django-axes` (Security/Brute-force protection)
    -   `django-cryptography` (Data encryption)
    -   `widget_tweaks` (Form styling)

## 3. Project Structure
The project follows a modular Django app structure:

| Directory | Purpose |
| :--- | :--- |
| `system` | **Configuration Core**. Contains `settings.py`, `urls.py` (root routing), and WSGI/ASGI info. |
| `core` | **System Utilities & Dashboards**. content access, authentication logic, middleware, and role-specific dashboards (`admin`, `staff`, `accountant`, `loan_officer`). |
| `client_accounts` | **Client Management**. Handles `ClientAccount`, `UserProfile`, and `SavingsTransaction`. This is the foundation of the system. |
| `loans` | **Loan Management**. The most complex app. Handles `LoanProduct` definitions, `LoanApplication` workflows, `Loan` lifecycle, and `LoanTransaction` (repayments/disbursements). |
| `reports` | **Reporting**. Likely handles the generation of operational and financial reports (not deeply analyzed, but standard convention). |
| `templates` | **UI Layer**. Global templates directory. `core`, `loans`, `client_accounts` have their own subdirectories here. |

## 4. Key Business Logic & Data Models

### A. Client Management (`client_accounts`)
-   **Entities**:
    -   `ClientAccount`: Supports **Single** and **Joint** accounts. Stores personal details, photos, signatures, and **Savings Balance**.
    -   `UserProfile`: Extends Django `User` to add roles (`ADMIN`, `STAFF`, `MANAGER`, `ACCOUNTANT`, `LOAN_OFFICER`).
    -   `SavingsTransaction`: Tracks deposits/withdrawals with support for reversals and audit logs.
-   **Key Logic**:
    -   **Audit Trails**: `ClientAuditLog` records every status change (Approval, Rejection, Edit).
    -   **Edit Workflows**: Sensitive data changes require an "Edit Request" -> "Approval" workflow (`ClientEditRequest`).

### B. Loan Management (`loans`)
-   **Entities**:
    -   `LoanProduct`: Configuration for loan types (Interest rates, calculation methods like `FLAT` vs `REDUCING`, fee structures).
    -   `LoanApplication`: Multi-step workflow (Draft -> Submitted -> Under Review -> Approved -> Disbursed). Includes credit scoring logic (`calculate_credit_score`).
    -   `Loan`: Represents an active loan. Tracks `remaining_balance`, `overdue_amount`, and links to repayment schedules.
    -   `Guarantor`: Support for Individual, Company, or Group guarantors.
-   **Key Logic**:
    -   **Eligibility**: `can_take_loan` checks if savings cover at least 20% of the loan amount (`min_savings_balance_percent`).
    -   **Credit Scoring**: Automates risk assessment based on account age, savings ratio, debt-to-income, and collateral.
    -   **Amortization**: Custom service (`AmortizationService`) calculates repayment schedules based on product terms (Weekly/Monthly, Flat/Reducing).

### C. Access Control
-   **Role-Based Access**: Views in `core` (`dashboard_redirect`) enforce strict separation.
    -   **Admins**: Global view, staff management.
    -   **Staff**: Client registration, basic management.
    -   **Loan Officers**: Manage "My Clients", loan applications.
    -   **Accountants**: View/Approves transactions, financial overview.

## 5. Security & Stability Features
-   **CSP**: Content Security Policy is configured in `settings.py` (currently in dev mode).
-   **Audit Logging**: Extensive logging of critical actions (money movement, account changes).
-   **Atomic Transactions**: Financial operations (`save` methods in `SavingsTransaction`) use `transaction.atomic()` to ensure data integrity.

## 6. Observations & Recommendations
-   **"Fix" Scripts**: The presence of `fix.ps1`, `fix_template.py`, etc., suggests recent struggles with template inheritance or bulk data corrections.
-   **White Page Errors**: The user context mentions these. They are likely due to `dashboard_redirect` failing silently or templates not extending their parent `base.html` correctly (a common django issue).
-   **Scalability**: The modular app design is good. The decision to separate `client_accounts` from `loans` is excellent for long-term maintenance.
