# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-09-29 18:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wps', '0037_cdat_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='steps_completed',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='job',
            name='steps_total',
            field=models.IntegerField(default=0),
        ),
    ]