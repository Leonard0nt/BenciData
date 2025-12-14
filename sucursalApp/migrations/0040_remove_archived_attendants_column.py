from django.db import migrations


def drop_archived_attendants_column(apps, schema_editor):
    """Remove legacy archived_attendants column left in the database schema."""

    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        'ALTER TABLE "sucursalApp_servicesession" DROP COLUMN IF EXISTS "archived_attendants";'
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sucursalApp", "0039_servicesession_attendants_snapshot"),
    ]

    operations = [
        migrations.RunPython(drop_archived_attendants_column, migrations.RunPython.noop),
    ]