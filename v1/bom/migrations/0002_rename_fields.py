from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bom', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='productbom',
            old_name='is_additive',
            new_name='additive_yn',
        ),
        migrations.RenameField(
            model_name='productbom',
            old_name='is_gmo',
            new_name='gmo_yn',
        ),
        migrations.RenameField(
            model_name='productbom',
            old_name='is_active',
            new_name='active_yn',
        ),
    ]
