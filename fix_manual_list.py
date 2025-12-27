import os

files_to_fix = [
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\quick_payment.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\portfolio_report.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\overdue_report.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loan_list.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanproduct_list.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanapplication_list.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\loanapplication_form.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\guarantor_list.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\detail.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\create.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\collections_report.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\bulk_payment.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\loans\bulk_disbursement.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\savings_list.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\audit_logs.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_savings.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_edit.html",
    r"c:\Users\hp\Desktop\haliur_investments\templates\client_accounts\account_confirm_delete.html"
]

def fix_file(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = content
        if "templates\\loans" in file_path:
             target_base = "{% extends 'loans/base.html' %}"
        else:
             target_base = "{% extends 'client_accounts/base.html' %}"

        if "{% extends 'base.html' %}" in content:
            print(f"Fixing {file_path}")
            new_content = content.replace("{% extends 'base.html' %}", target_base)
        elif '{% extends "base.html" %}' in content:
             print(f"Fixing {file_path} (double quotes)")
             new_content = content.replace('{% extends "base.html" %}', target_base)
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    for f in files_to_fix:
        fix_file(f)
