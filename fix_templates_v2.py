import os
import re

def fix_templates(directory, app_name):
    print(f"Scanning {directory}...")
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return

    count = 0
    # Regex to match {% extends 'base.html' %} with any spacing and quotes
    pattern = re.compile(r"{%\s*extends\s*['\"]base\.html['\"]\s*%}")
    replacement = f"{{% extends '{app_name}/base.html' %}}"

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                # Skip the base.html of the app itself
                if file == 'base.html':
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if pattern.search(content):
                    print(f"Fixing {file_path}")
                    new_content = pattern.sub(replacement, content)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
    print(f"Fixed {count} files in {app_name}")

if __name__ == "__main__":
    base_dir = r"c:\Users\hp\Desktop\haliur_investments\templates"
    fix_templates(os.path.join(base_dir, "loans"), "loans")
    fix_templates(os.path.join(base_dir, "client_accounts"), "client_accounts")
