from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('loans', '0006_loanpayment_payment_method')]
    operations = [migrations.AlterField(model_name='guarantor', name='guarantor_type', field=models.CharField(choices=[('INTERNAL', 'Internal'), ('EXTERNAL', 'External')], max_length=20))]