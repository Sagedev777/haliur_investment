from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [

    # ----------------------------
    # AUTHENTICATION
    # ----------------------------
    path('login/', auth_views.LoginView.as_view(
        template_name='client_accounts/login.html'
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),


    # ----------------------------
    # DASHBOARD
    # ----------------------------
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),


    # ----------------------------
    # CLIENT ACCOUNTS
    # ----------------------------
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('accounts/export/csv/', views.export_accounts_csv, name='export_accounts_csv'),

    # Admin-only approvals
    path('accounts/<int:pk>/approve/', views.account_approve, name='account_approve'),
    path('accounts/<int:pk>/reject/', views.account_reject, name='account_reject'),


    # ----------------------------
    # SAVINGS TRANSACTIONS
    # ----------------------------
    path('savings/', views.savings_list, name='savings_list'),
    path('savings/deposit/<int:account_id>/', views.savings_deposit, name='savings_deposit'),
    path('savings/withdrawal/<int:account_id>/', views.savings_withdrawal, name='savings_withdrawal'),
    path('savings/transactions/', views.savings_transactions, name='savings_transactions'),
    path('savings/account/<int:account_id>/', views.account_savings, name='account_savings'),


    # ----------------------------
    # AJAX / API ENDPOINTS
    # ----------------------------
    path('api/accounts/', views.api_account_list, name='api_account_list'),
    path('api/account/<int:pk>/', views.api_account_detail, name='api_account_detail'),
    path('api/savings/balance/<int:account_id>/', views.api_savings_balance, name='api_savings_balance'),


    # ----------------------------
    # EXPORTS (CSV & PDF)
    # ----------------------------
    path('transactions/export/csv/<int:account_id>/', views.export_transactions_csv, name='export_transactions_csv'),
    path('transactions/export/pdf/<int:account_id>/', views.export_transactions_pdf, name='export_transactions_pdf'),
    path('transactions/export/csv/', views.export_transactions_csv, name='export_transactions_csv'),
    path('transactions/export/pdf/', views.export_transactions_pdf, name='export_transactions_pdf'),
]
