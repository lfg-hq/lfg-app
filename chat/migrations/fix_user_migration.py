from django.db import migrations

def set_default_user(apps, schema_editor):
    Conversation = apps.get_model('chat', 'Conversation')
    User = apps.get_model('auth', 'User')
    
    # Get first user or create one if none exists
    default_user = User.objects.first()
    if not default_user:
        default_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='password'
        )
    
    # Update all existing conversations
    Conversation.objects.filter(user__isnull=True).update(user=default_user)

class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_default_user),
    ] 