from django.contrib import admin

from .models import Island, Machine, Nozzle, Shift, Sucursal, SucursalStaff


class NozzleInline(admin.TabularInline):
    model = Nozzle
    extra = 1


class MachineInline(admin.TabularInline):
    model = Machine
    extra = 1


class IslandInline(admin.TabularInline):
    model = Island
    extra = 1


class ShiftInline(admin.TabularInline):
    model = Shift
    extra = 0


class SucursalStaffInline(admin.TabularInline):
    model = SucursalStaff
    extra = 1

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "city",
        "region",
        "island_count",
        "machines_count",
        "nozzles_count",
        "shifts_count",
    )
    search_fields = ("name", "company__business_name", "city", "region")
    list_filter = ("company", "city", "region")
    inlines = [SucursalStaffInline, ShiftInline, IslandInline]

    @admin.display(description="Islas")
    def island_count(self, obj: Sucursal) -> int:
        return obj.branch_islands.count()

    @admin.display(description="Máquinas")
    def machines_count(self, obj: Sucursal) -> int:
        return obj.machines_count

    @admin.display(description="Pistolas")
    def nozzles_count(self, obj: Sucursal) -> int:
        return obj.nozzles_count
    
    @admin.display(description="Turnos")
    def shifts_count(self, obj: Sucursal) -> int:
        return obj.shifts_count



@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    list_display = ("number", "sucursal", "description")
    list_filter = ("sucursal",)
    search_fields = ("number", "sucursal__name")
    inlines = [MachineInline]


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("number", "island", "fuel_type", "initial_numeral", "final_numeral")
    list_filter = ("island__sucursal", "fuel_type")
    search_fields = ("number", "island__sucursal__name")
    inlines = [NozzleInline]


@admin.register(Nozzle)
class NozzleAdmin(admin.ModelAdmin):
    list_display = ("number", "machine", "fuel_type")
    list_filter = ("machine__island__sucursal", "fuel_type")
    search_fields = ("number", "machine__island__sucursal__name")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("code", "sucursal", "start_time", "end_time", "manager")
    list_filter = ("sucursal",)
    search_fields = ("code", "sucursal__name", "manager__user_FK__username")