import os

def fix_templates(directory, app_name):
    print(f"Scanning {directory}...")
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                # Skip the base.html of the app itself to avoid circular references if it extends base.html (which is correct for app base)
                if file == 'base.html':
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if it extends 'base.html' directly
                if "{% extends 'base.html' %}" in content or '{% extends "base.html" %}' in content:
                    print(f"Fixing {file_path}")
                    new_content = content.replace("{% extends 'base.html' %}", f"{{% extends '{app_name}/base.html' %}}")
                    new_content = new_content.replace('{% extends "base.html" %}', f"{{% extends '{app_name}/base.html' %}}")
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
    print(f"Fixed {count} files in {app_name}")

if __name__ == "__main__":
    base_dir = r"c:\Users\hp\Desktop\haliur_investments\templates"
    fix_templates(os.path.join(base_dir, "loans"), "loans")
    fix_templates(os.path.join(base_dir, "client_accounts"), "client_accounts")
