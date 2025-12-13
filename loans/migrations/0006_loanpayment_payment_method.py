from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('loans', '0005_remove_loanapplication_approved_interest_rate_and_more')]
    operations = [migrations.AddField(model_name='loanpayment', name='payment_method', field=models.CharField(choices=[('CASH', 'Cash'), ('BANK_TRANSFER', 'Bank Transfer'), ('MOBILE_MONEY', 'Mobile Money'), ('CHEQUE', 'Cheque')], default='CASH', max_length=20))]