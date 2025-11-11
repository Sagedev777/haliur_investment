from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment
from client_accounts.models import ClientAccount
from .forms import LoanProductForm, LoanApplicationForm, GuarantorForm, LoanPaymentForm

# ---------------------
# Loan Product Views
# ---------------------
@login_required
def loan_products_list(request):
    products = LoanProduct.objects.all()
    return render(request, 'loans/loan_products_list.html', {'products': products})

@login_required
def loan_product_create(request):
    if request.method == 'POST':
        form = LoanProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('loan_products_list')
    else:
        form = LoanProductForm()
    return render(request, 'loans/loan_product_form.html', {'form': form})

@login_required
def loan_product_edit(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    if request.method == 'POST':
        form = LoanProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('loan_products_list')
    else:
        form = LoanProductForm(instance=product)
    return render(request, 'loans/loan_product_form.html', {'form': form})

@login_required
def loan_product_delete(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    product.delete()
    return redirect('loan_products_list')

# ---------------------
# Loan Application Views
# ---------------------
@login_required
def loan_applications_list(request):
    applications = LoanApplication.objects.all()
    return render(request, 'loans/loan_applications_list.html', {'applications': applications})

@login_required
def loan_application_create(request):
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            loan_app = form.save(commit=False)
            loan_app.loan_officer = request.user
            loan_app.save()
            return redirect('loan_applications_list')
    else:
        form = LoanApplicationForm()
    return render(request, 'loans/loan_application_form.html', {'form': form})

@login_required
def loan_application_detail(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    return render(request, 'loans/loan_application_detail.html', {'application': application})

@login_required
def loan_application_edit(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST, request.FILES, instance=application)
        if form.is_valid():
            form.save()
            return redirect('loan_applications_list')
    else:
        form = LoanApplicationForm(instance=application)
    return render(request, 'loans/loan_application_form.html', {'form': form})

@login_required
def loan_application_delete(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    application.delete()
    return redirect('loan_applications_list')

@login_required
def loan_application_approve(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    app.status = 'APPROVED'
    app.approval_date = timezone.now()
    app.approved_by = request.user
    app.save()
    return redirect('loan_applications_list')

@login_required
def loan_application_reject(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    app.status = 'REJECTED'
    app.approved_by = request.user
    app.save()
    return redirect('loan_applications_list')

@login_required
def loan_application_disburse(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    app.status = 'DISBURSED'
    app.disbursement_date = timezone.now()
    app.disbursed_by = request.user
    app.save()
    return redirect('loan_applications_list')

# ---------------------
# Guarantor Views
# ---------------------
@login_required
def guarantors_list(request):
    guarantors = Guarantor.objects.all()
    return render(request, 'loans/guarantors_list.html', {'guarantors': guarantors})

@login_required
def guarantor_create(request):
    if request.method == 'POST':
        form = GuarantorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('guarantors_list')
    else:
        form = GuarantorForm()
    return render(request, 'loans/guarantor_form.html', {'form': form})

@login_required
def guarantor_edit(request, pk):
    guarantor = get_object_or_404(Guarantor, pk=pk)
    if request.method == 'POST':
        form = GuarantorForm(request.POST, instance=guarantor)
        if form.is_valid():
            form.save()
            return redirect('guarantors_list')
    else:
        form = GuarantorForm(instance=guarantor)
    return render(request, 'loans/guarantor_form.html', {'form': form})

@login_required
def guarantor_delete(request, pk):
    guarantor = get_object_or_404(Guarantor, pk=pk)
    guarantor.delete()
    return redirect('guarantors_list')

# ---------------------
# Payment Views
# ---------------------
@login_required
def payments_list(request):
    payments = LoanPayment.objects.all()
    return render(request, 'loans/payments_list.html', {'payments': payments})

@login_required
def payment_create(request):
    if request.method == 'POST':
        form = LoanPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.received_by = request.user
            payment.save()
            return redirect('payments_list')
    else:
        form = LoanPaymentForm()
    return render(request, 'loans/payment_form.html', {'form': form})

@login_required
def payment_edit(request, pk):
    payment = get_object_or_404(LoanPayment, pk=pk)
    if request.method == 'POST':
        form = LoanPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect('payments_list')
    else:
        form = LoanPaymentForm(instance=payment)
    return render(request, 'loans/payment_form.html', {'form': form})

@login_required
def payment_delete(request, pk):
    payment = get_object_or_404(LoanPayment, pk=pk)
    payment.delete()
    return redirect('payments_list')

@login_required
def loan_payments(request, loan_id):
    loan = get_object_or_404(LoanApplication, pk=loan_id)
    payments = loan.loanpayment_set.all()
    return render(request, 'loans/loan_payments.html', {'loan': loan, 'payments': payments})

# ---------------------
# Loan Management Views
# ---------------------
@login_required
def active_loans(request):
    loans = LoanApplication.objects.filter(status='DISBURSED')
    return render(request, 'loans/active_loans.html', {'loans': loans})

@login_required
def completed_loans(request):
    loans = LoanApplication.objects.filter(status='COMPLETED')
    return render(request, 'loans/completed_loans.html', {'loans': loans})

@login_required
def defaulted_loans(request):
    loans = LoanApplication.objects.filter(status='DEFAULTED')
    return render(request, 'loans/defaulted_loans.html', {'loans': loans})

@login_required
def overdue_loans(request):
    loans = LoanApplication.objects.filter(status='DISBURSED')
    overdue = [loan for loan in loans if loan.is_overdue()]
    return render(request, 'loans/overdue_loans.html', {'loans': overdue})

# ---------------------
# API Views (JSON)
# ---------------------
@login_required
def api_loan_products(request):
    products = list(LoanProduct.objects.values())
    return JsonResponse(products, safe=False)

@login_required
def api_loan_product_detail(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    return JsonResponse({
        'id': product.id,
        'name': product.name,
        'interest_rate': str(product.interest_rate),
        'min_amount': str(product.min_amount),
        'max_amount': str(product.max_amount),
        'loan_period': product.loan_period,
        'number_of_installments': product.number_of_installments,
        'is_active': product.is_active,
    })

@login_required
def api_loan_applications(request):
    applications = list(LoanApplication.objects.values())
    return JsonResponse(applications, safe=False)

@login_required
def api_loan_application_detail(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    return JsonResponse({
        'id': app.id,
        'application_number': app.application_number,
        'client_account': app.client_account.full_account_name,
        'loan_amount': str(app.loan_amount),
        'status': app.status,
    })

@login_required
def api_guarantors(request):
    guarantors = list(Guarantor.objects.values())
    return JsonResponse(guarantors, safe=False)

@login_required
def api_loan_payments(request, loan_id):
    loan = get_object_or_404(LoanApplication, pk=loan_id)
    payments = list(loan.loanpayment_set.values())
    return JsonResponse(payments, safe=False)
