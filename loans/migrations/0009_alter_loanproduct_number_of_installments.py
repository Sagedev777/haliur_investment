from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('loans', '0008_alter_loanapplication_interest_amount_and_more')]
    operations = [migrations.AlterField(model_name='loanproduct', name='number_of_installments', field=models.IntegerField(blank=True, null=True))]