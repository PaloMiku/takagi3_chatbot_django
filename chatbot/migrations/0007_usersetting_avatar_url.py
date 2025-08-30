from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('chatbot', '0006_add_user_api_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersetting',
            name='avatar_url',
            field=models.TextField(blank=True, null=True),
        ),
    ]
