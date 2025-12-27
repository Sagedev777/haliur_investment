import os

# Explicit list of files and their correct base template
fixes = {
    # Loans App
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loan_list.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\quick_payment.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\portfolio_report.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\overdue_report.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanproduct_list.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanapplication_list.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanapplication_form.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\guarantor_list.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\detail.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\create.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\collections_report.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\bulk_payment.html": "{% extends 'loans/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\bulk_disbursement.html": "{% extends 'loans/base.html' %}",
    
    # Client Accounts App
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\savings_list.html": "{% extends 'client_accounts/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\audit_logs.html": "{% extends 'client_accounts/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_savings.html": "{% extends 'client_accounts/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_edit.html": "{% extends 'client_accounts/base.html' %}",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_confirm_delete.html": "{% extends 'client_accounts/base.html' %}"
}

def force_fix():
    for file_path, correct_extends in fixes.items():
        if not os.path.exists(file_path):
            print(f"Skipping (not found): {file_path}")
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Replace the first line if it's an extends tag (or search first 5 lines)
            fixed = False
            new_lines = []
            for i, line in enumerate(lines):
                if i < 5 and "{% extends" in line and "base.html" in line:
                    print(f"Fixing {file_path}")
                    new_lines.append(correct_extends + "\n")
                    fixed = True
                else:
                    new_lines.append(line)
            
            if fixed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
            else:
                print(f"No extends tag found in first 5 lines of {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    force_fix()
