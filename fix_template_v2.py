
import os
import re

file_path = r'C:\Users\hp\Desktop\haliur_investment\templates\loans\loan_list.html'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"Read content length: {len(content)}")

    # Fix 1: Product filter
    pattern1 = r'request\.GET\.product==product\.pk\|stringformat:"s"\s*%\}selected\{%\s*endif\s*%\}'
    replacement1 = r'request.GET.product == product.pk|stringformat:"s" %}selected{% endif %}'
    
    new_content = re.sub(pattern1, replacement1, content)
    if new_content != content:
        print("Fix 1 applied via regex.")
        content = new_content
    else:
        print("Fix 1 NOT applied.")

    # Fix 2: Overdue filter
    pattern2 = r'value="true"\s*\{%\s*if\s+request\.GET\.show_overdue\s*%\}\s*checked\s*\{%\s*endif\s*%\}'
    replacement2 = r'value="true" {% if request.GET.show_overdue %}checked{% endif %}'
    
    new_content = re.sub(pattern2, replacement2, content)
    if new_content != content:
        print("Fix 2 applied via regex.")
        content = new_content
    else:
        print("Fix 2 NOT applied.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("File saved.")

except Exception as e:
    print(f"Error: {e}")
