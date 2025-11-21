from django.urls import path
from . import views

app_name = 'loans'

urlpatterns = [
    # ---------------------
    # Loan Products URLs
    # ---------------------
    path('products/', views.loan_products_list, name='loan_products_list'),
    path('products/create/', views.loan_product_create, name='loan_product_create'),
    path('products/<int:pk>/edit/', views.loan_product_edit, name='loan_product_edit'),
    path('products/<int:pk>/delete/', views.loan_product_delete, name='loan_product_delete'),

    # ---------------------
    # Loan Applications URLs
    # ---------------------
    path('applications/', views.loan_applications_list, name='list_loans'),
    path('applications/create/', views.loan_application_create, name='loan_application_create'),
    path('applications/<int:pk>/', views.loan_application_detail, name='loan_application_detail'),
    path('applications/<int:pk>/edit/', views.loan_application_edit, name='loan_application_edit'),
    path('applications/<int:pk>/delete/', views.loan_application_delete, name='loan_application_delete'),

    # Loan Approval / Disbursement URLs
    path('applications/<int:pk>/approve/', views.loan_application_approve, name='loan_application_approve'),
    path('applications/<int:pk>/reject/', views.loan_application_reject, name='loan_application_reject'),
    path('applications/<int:pk>/disburse/', views.loan_application_disburse, name='loan_application_disburse'),

    # ---------------------
    # Guarantor URLs
    # ---------------------
    path('guarantors/', views.guarantors_list, name='guarantors_list'),
    path('guarantors/create/', views.guarantor_create, name='guarantor_create'),
    path('guarantors/<int:pk>/edit/', views.guarantor_edit, name='guarantor_edit'),
    path('guarantors/<int:pk>/delete/', views.guarantor_delete, name='guarantor_delete'),

    # ---------------------
    # Loan Payments URLs
    # ---------------------
    path('payments/', views.payments_list, name='payments_list'),
    path('payments/create/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/edit/', views.payment_edit, name='payment_edit'),
    path('payments/<int:pk>/delete/', views.payment_delete, name='payment_delete'),
    path('payments/loan/<int:loan_id>/', views.loan_payments, name='loan_payments'),

    # ---------------------
    # Loan Status Management URLs
    # ---------------------
    path('active/', views.active_loans, name='active_loans'),
    path('completed/', views.completed_loans, name='completed_loans'),
    path('defaulted/', views.defaulted_loans, name='defaulted_loans'),
    path('overdue/', views.overdue_loans, name='overdue_loans'),

    # ---------------------
    # API / AJAX URLs
    # ---------------------
    path('api/products/', views.api_loan_products, name='api_loan_products'),
    path('api/product/<int:pk>/', views.api_loan_product_detail, name='api_loan_product_detail'),
    path('api/applications/', views.api_loan_applications, name='api_loan_applications'),
    path('api/application/<int:pk>/', views.api_loan_application_detail, name='api_loan_application_detail'),
    path('api/guarantors/', views.api_guarantors, name='api_guarantors'),
    path('api/payments/loan/<int:loan_id>/', views.api_loan_payments, name='api_loan_payments'),

    # ---------------------
    # Export URLs
    # ---------------------
    path('export/csv/', views.export_loans_csv, name='export_loans_csv'),
]
