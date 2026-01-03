
import os

file_path = r'C:\Users\hp\Desktop\haliur_investment\templates\loans\loan_list.html'
output_path = r'C:\Users\hp\Desktop\haliur_investment\debug_output.txt'
    
try:
    with open(file_path, 'rb') as f:
        content = f.read()

    # Find the chunk around "request.GET.product"
    start = content.find(b'request.GET.product')
    if start != -1:
        chunk = content[start:start+100]
        result = f"Chunk found: {chunk!r}"
    else:
        result = "Chunk NOT found"
        
    with open(output_path, 'w') as f:
        f.write(result)
        
    print(result)
except Exception as e:
    print(f"Error: {e}")
