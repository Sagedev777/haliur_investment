from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment
from client_accounts.models import ClientAccount
from .forms import LoanProductForm, LoanApplicationForm, GuarantorForm, LoanPaymentForm
import csv

# ---------------------
# Loan Product Views
# ---------------------
@login_required
def loan_products_list(request):
    products = LoanProduct.objects.all()
    return render(request, 'loans/loan_products_list.html', {'products': products})

@login_required
def loan_product_create(request):
    form = LoanProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('loans:loan_products_list')
    return render(request, 'loans/loan_product_form.html', {'form': form})

@login_required
def loan_product_edit(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    form = LoanProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('loans:loan_products_list')
    return render(request, 'loans/loan_product_form.html', {'form': form})

@login_required
def loan_product_delete(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    product.delete()
    return redirect('loans:loan_products_list')


# ---------------------
# Loan Application Views
# ---------------------
@login_required
def loan_applications_list(request):
    applications = LoanApplication.objects.all().order_by('-application_date')
    return render(request, 'loans/loan_applications_list.html', {'applications': applications})

@login_required
def loan_application_create(request):
    form = LoanApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        loan_app = form.save(commit=False)
        loan_app.loan_officer = request.user
        loan_app.save()
        return redirect('loan_applications_list')
    return render(request, 'loans/loan_application_form.html', {'form': form})

@login_required
def loan_application_detail(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    payments = application.loanpayment_set.all()
    return render(request, 'loans/loan_application_detail.html', {'application': application, 'payments': payments})

@login_required
def loan_application_edit(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    form = LoanApplicationForm(request.POST or None, request.FILES or None, instance=application)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('loan_applications_list')
    return render(request, 'loans/loan_application_form.html', {'form': form})

@login_required
def loan_application_delete(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    application.delete()
    return redirect('loans:list_loans')

@login_required
def loan_application_approve(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    if app.status == 'PENDING':
        app.status = 'APPROVED'
        app.approval_date = timezone.now()
        app.approved_by = request.user
        app.save()
    return redirect('loan_applications_list')

@login_required
def loan_application_reject(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    if app.status == 'PENDING':
        app.status = 'REJECTED'
        app.approved_by = request.user
        app.save()
    return redirect('loan_applications_list')

@login_required
def loan_application_disburse(request, pk):
    app = get_object_or_404(LoanApplication, pk=pk)
    if app.status == 'APPROVED':
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
    form = GuarantorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('guarantors_list')
    return render(request, 'loans/guarantor_form.html', {'form': form})

@login_required
def guarantor_edit(request, pk):
    guarantor = get_object_or_404(Guarantor, pk=pk)
    form = GuarantorForm(request.POST or None, instance=guarantor)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('guarantors_list')
    return render(request, 'loans/guarantor_form.html', {'form': form})

@login_required
def guarantor_delete(request, pk):
    guarantor = get_object_or_404(Guarantor, pk=pk)
    guarantor.delete()
    return redirect('guarantors_list')


# ---------------------
# Loan Payment Views
# ---------------------
@login_required
def payments_list(request):
    payments = LoanPayment.objects.all().order_by('-payment_date')
    return render(request, 'loans/payments_list.html', {'payments': payments})

@login_required
def payment_create(request):
    form = LoanPaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        return redirect('payments_list')
    return render(request, 'loans/payment_form.html', {'form': form})

@login_required
def payment_edit(request, pk):
    payment = get_object_or_404(LoanPayment, pk=pk)
    form = LoanPaymentForm(request.POST or None, instance=payment)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('payments_list')
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
# Loan Status Views
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
    apps = list(LoanApplication.objects.values())
    return JsonResponse(apps, safe=False)

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


# ---------------------
# CSV Export
# ---------------------
@login_required
def export_loans_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loan_products.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Interest Rate', 'Loan Period', 'Min Amount', 'Max Amount', 'Active'])

    for loan in LoanProduct.objects.all():
        writer.writerow([loan.name, loan.interest_rate, loan.loan_period, loan.min_amount, loan.max_amount, loan.is_active])

    return response
