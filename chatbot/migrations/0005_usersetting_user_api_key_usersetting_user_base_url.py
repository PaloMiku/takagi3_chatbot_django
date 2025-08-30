from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0004_alter_usersetting_modelname'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersetting',
            name='user_api_key',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usersetting',
            name='user_base_url',
            field=models.TextField(blank=True, null=True),
        ),
    ]
