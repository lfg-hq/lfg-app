# Generated by Django 4.2.7 on 2025-05-23 01:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chat', '0010_alter_agentrole_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModelSelection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selected_model', models.CharField(choices=[('claude_4_sonnet', 'Claude 4 Sonnet'), ('gpt_4_1', 'OpenAI GPT-4.1'), ('gpt_4o', 'OpenAI GPT-4o')], default='claude_4_sonnet', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='model_selection', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
