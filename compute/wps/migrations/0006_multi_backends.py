# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-30 23:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wps', '0005_oauth2'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='process',
            name='completed',
        ),
        migrations.RemoveField(
            model_name='process',
            name='started',
        ),
        migrations.AddField(
            model_name='process',
            name='backend',
            field=models.CharField(default='cdas2', max_length=128),
            preserve_default=False,
        ),
    ]
