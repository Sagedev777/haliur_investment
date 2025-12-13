from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('client_accounts', '0006_alter_clientaccount_options_and_more')]
    operations = [migrations.AlterField(model_name='clientaccount', name='created_by', field=models.ForeignKey(default=1, help_text='User who created this account', on_delete=django.db.models.deletion.PROTECT, related_name='created_accounts', to=settings.AUTH_USER_MODEL), preserve_default=False)]