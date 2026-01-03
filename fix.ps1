
$path = "C:\Users\hp\Desktop\haliur_investment\templates\loans\loan_list.html"
$content = Get-Content -Path $path -Raw

# Fix 1
# match: request.GET.product==product.pk|stringformat:"s" %}selected{% <newline/spaces> endif %}
$content = $content -replace 'request\.GET\.product==product\.pk\|stringformat:"s"\s*%\}selected\{%\s*endif\s*%\}', 'request.GET.product == product.pk|stringformat:"s" %}selected{% endif %}'

# Fix 2
# match: value="true" {% <newline/spaces> if request.GET.show_overdue %}checked{% endif %}
$content = $content -replace 'value="true"\s*\{%\s*if\s+request\.GET\.show_overdue\s*%\}\s*checked\s*\{%\s*endif\s*%\}', 'value="true" {% if request.GET.show_overdue %}checked{% endif %}'

Set-Content -Path $path -Value $content -Encoding UTF8
Write-Host "File updated using PowerShell."
