from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('client_accounts', '0002_alter_clientaccount_loan_officer')]
    operations = [migrations.AddField(model_name='clientaccount', name='is_approved', field=models.BooleanField(default=True))]