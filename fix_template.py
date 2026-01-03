
import os

file_path = r'C:\Users\hp\Desktop\haliur_investment\templates\loans\loan_list.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Product filter
old_str_1 = 'pk|stringformat:"s" %}selected{%\n                        endif %}'
new_str_1 = 'pk|stringformat:"s" %}selected{% endif %}'

# Improved matching for potential whitespace variations (simple approach first)
# The view_file output showed: 
# ... selected{%
#                         endif %}
# So let's try to match that specific pattern.

content = content.replace('request.GET.product==product.pk|stringformat:"s"', 'request.GET.product == product.pk|stringformat:"s"')
content = content.replace('selected{%\n                        endif %}', 'selected{% endif %}')

# Fix 2: Overdue filter
content = content.replace('{% if request.GET.show_overdue %}checked{% endif %}', 'CHECKED_PLACEHOLDER') # If already fixed
# But we saw it was split:
# value="true" {%
#                         if request.GET.show_overdue %}checked{% endif %}
content = content.replace('value="true" {%\n                        if request.GET.show_overdue %}checked{% endif %}', 'value="true" {% if request.GET.show_overdue %}checked{% endif %}')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File updated.")
