# Generated by Django 4.2.7 on 2025-04-17 20:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_projecttickets_projectdesignschema'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecttickets',
            name='backend_tasks',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='projecttickets',
            name='frontend_tasks',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='projecttickets',
            name='implementation_steps',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='projecttickets',
            name='status',
            field=models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('agent', 'Agent'), ('closed', 'Closed')], default='open', max_length=20),
        ),
        migrations.AlterField(
            model_name='projecttickets',
            name='test_case',
            field=models.TextField(default=''),
        ),
    ]
