from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('loans', '0009_alter_loanproduct_number_of_installments')]
    operations = [migrations.AlterField(model_name='loanproduct', name='number_of_installments', field=models.IntegerField(default=0, editable=False))]