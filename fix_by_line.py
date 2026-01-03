
path = r'C:\Users\hp\Desktop\haliur_investment\templates\loans\loan_list.html'
try:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"Total lines: {len(lines)}")
    
    # Fix 1: Product filter
    # Look for the split line at index 113 (line 114)
    if 113 < len(lines) and 'request.GET.product' in lines[113]:
        print("Found product filter at line 114")
        lines[113] = '                    <option value="{{ product.pk }}" {% if request.GET.product == product.pk|stringformat:"s" %}selected{% endif %}>\n'
        # The next line (114) had the closing tag. We merged it. So empty it.
        # Original 115:                         endif %}>
        if 114 < len(lines):
             lines[114] = '' 
    
    # Fix 2: Overdue filter
    # Look for split line at index 131 (line 132)
    if 131 < len(lines) and 'show_overdue' in lines[131] and '{%' in lines[131]:
        print("Found overdue filter at line 132")
        lines[131] = '                    <input class="form-check-input" type="checkbox" name="show_overdue" id="showOverdue" value="true" {% if request.GET.show_overdue %}checked{% endif %}>\n'
        if 132 < len(lines):
            lines[132] = ''

    # Write back
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
    print("File updated.")

except Exception as e:
    print(f"Error: {e}")
