import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


def copy_machine_inventory_numerals(apps, schema_editor):
    Machine = apps.get_model("sucursalApp", "Machine")
    MachineFuelInventory = apps.get_model("sucursalApp", "MachineFuelInventory")

    through_model = Machine.fuel_inventories.through
    bulk_links = []
    for link in through_model.objects.all():
        bulk_links.append(
            MachineFuelInventory(
                machine_id=link.machine_id,
                fuel_inventory_id=link.fuelinventory_id,
                numeral=link.machine.numeral if link.machine_id else Decimal("0"),
            )
        )
    if bulk_links:
        MachineFuelInventory.objects.bulk_create(bulk_links, ignore_conflicts=True)


def noop_backward(apps, schema_editor):
    # No-op reversal; keep existing numerals in machine table only.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sucursalApp", "0028_machine_fuel_inventories_nozzle_fuel_inventory_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineFuelInventory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "numeral",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12, verbose_name="Numeral"
                    ),
                ),
                (
                    "fuel_inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="machinefuelinventory_set",
                        to="sucursalApp.fuelinventory",
                        verbose_name="Estanque",
                    ),
                ),
                (
                    "machine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="machinefuelinventory_set",
                        to="sucursalApp.machine",
                        verbose_name="Máquina",
                    ),
                ),
            ],
            options={
                "verbose_name": "Numeral de estanque",
                "verbose_name_plural": "Numerales de estanque",
                "unique_together": {("machine", "fuel_inventory")},
            },
        ),
        migrations.RunPython(copy_machine_inventory_numerals, reverse_code=noop_backward),
        migrations.RemoveField(
            model_name="machine",
            name="fuel_inventories",
        ),
        migrations.AddField(
            model_name="machine",
            name="fuel_inventories",
            field=models.ManyToManyField(
                blank=True,
                related_name="associated_machines",
                through="sucursalApp.MachineFuelInventory",
                to="sucursalApp.fuelinventory",
                verbose_name="Estanques",
            ),
        ),
    ]
