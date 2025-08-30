from django.db import migrations, models
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0002_botsetting_usersetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conversation_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                ('role', models.CharField(choices=[('system','System'),('user','User'),('assistant','Assistant')], max_length=20)),
                ('content', models.TextField()),
                ('tokens', models.IntegerField(default=0)),
                ('is_summary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='messages', to='auth.user')),
            ],
            options={'ordering':['created_at']},
        ),
    ]
