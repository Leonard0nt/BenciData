# Vista previa: numerales por estanque en máquinas

Esta guía muestra cómo ver el formulario con numerales separados por estanque en una máquina con múltiples tanques.

## Datos de ejemplo rápidos
Ejecuta en el shell de Django para crear una empresa demo, un usuario dueño y una sucursal con una máquina conectada a dos estanques:

```python
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
from UsuarioApp.models import Position, Profile
from homeApp.models import Company
from sucursalApp.models import Sucursal, Island, FuelInventory, Machine, MachineFuelInventory, Nozzle

pos, _ = Position.objects.get_or_create(user_position="Dueño", permission_code="OWNER")
user, _ = User.objects.get_or_create(username="owner", defaults={"email": "owner@example.com"})
user.set_password("ownerpass")
user.save()
profile, _ = Profile.objects.get_or_create(user_FK=user, defaults={"position_FK": pos})
profile.position_FK = pos
profile.save()
EmailAddress.objects.update_or_create(user=user, email=user.email, defaults={"verified": True, "primary": True})
company, _ = Company.objects.get_or_create(
    profile=profile,
    defaults={"rut": "76.543.210-9", "business_name": "Combustibles Demo", "tax_address": "Av. Principal 123"},
)
branch, _ = Sucursal.objects.get_or_create(
    company=company,
    name="Sucursal Central",
    defaults={"address": "Av. Central 100", "city": "Santiago", "region": "RM", "phone": "123456789", "email": "demo@example.com", "islands": 1},
)
island, _ = Island.objects.get_or_create(sucursal=branch, number=1, defaults={"description": "Isla demo"})
inv1, _ = FuelInventory.objects.get_or_create(sucursal=branch, code="TANQUE-01", defaults={"fuel_type": "93", "capacity": 10000, "liters": 7000})
inv2, _ = FuelInventory.objects.get_or_create(sucursal=branch, code="TANQUE-02", defaults={"fuel_type": "95", "capacity": 12000, "liters": 9000})
machine, _ = Machine.objects.get_or_create(island=island, number=1, defaults={"fuel_inventory": inv1, "numeral": 123.45})
MachineFuelInventory.objects.update_or_create(machine=machine, fuel_inventory=inv1, defaults={"numeral": 123.45})
MachineFuelInventory.objects.update_or_create(machine=machine, fuel_inventory=inv2, defaults={"numeral": 234.56})
Nozzle.objects.get_or_create(machine=machine, number=1, defaults={"fuel_inventory": inv1})
Nozzle.objects.get_or_create(machine=machine, number=2, defaults={"fuel_inventory": inv2})
```

## Navegación para ver la UI
1. Inicia el servidor (`python manage.py runserver`) y entra a `http://localhost:8000/accounts/login/`.
2. Accede con `owner@example.com` / `ownerpass`.
3. Abre `http://localhost:8000/sucursales/<id_de_la_sucursal>/editar/` y selecciona la pestaña **Islas y equipos**.
4. En la sección de la máquina verás los numerales separados por cada estanque asociado, uno por línea, tal como se muestra en la captura de ejemplo generada.
