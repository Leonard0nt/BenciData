from django.contrib import admin

from .models import (
    BranchProduct,
    FuelInventory,
    Island,
    Machine,
    Nozzle,
    Shift,
    ServiceSession,
    ServiceSessionFirefighterPayment,
    ServiceSessionCreditSale,
    ServiceSessionFuelLoad,
    ServiceSessionProductLoad,
    ServiceSessionProductSale,
    ServiceSessionProductSaleItem,
    ServiceSessionTransbankVoucher,
    Sucursal,
    SucursalStaff,
)


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


class FuelInventoryInline(admin.TabularInline):
    model = FuelInventory
    extra = 0


class BranchProductInline(admin.TabularInline):
    model = BranchProduct
    extra = 0

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
        "fuel_inventory_count",
        "products_count",   
    )
    search_fields = ("name", "company__business_name", "city", "region")
    list_filter = ("company", "city", "region")
    inlines = [
        SucursalStaffInline,
        ShiftInline,
        FuelInventoryInline,
        BranchProductInline,
        IslandInline,
    ]

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

    @admin.display(description="Inventarios de combustible")
    def fuel_inventory_count(self, obj: Sucursal) -> int:
        return obj.fuel_inventories_count

    @admin.display(description="Productos")
    def products_count(self, obj: Sucursal) -> int:
        return obj.products_count

@admin.register(FuelInventory)
class FuelInventoryAdmin(admin.ModelAdmin):
    list_display = ("code", "sucursal", "fuel_type", "capacity", "liters")
    list_filter = ("sucursal__company", "fuel_type")
    search_fields = ("code", "sucursal__name", "fuel_type")



@admin.register(BranchProduct)
class BranchProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_type",
        "sucursal",
        "quantity",
        "arrival_date",
        "batch_number",
        "value",
    )
    list_filter = ("sucursal__company", "arrival_date")
    search_fields = ("product_type", "sucursal__name", "batch_number")

@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    list_display = ("number", "sucursal", "description")
    list_filter = ("sucursal",)
    search_fields = ("number", "sucursal__name")
    inlines = [MachineInline]


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("number", "island", "fuel_type", "numeral")
    list_filter = ("island__sucursal", "fuel_type")
    search_fields = ("number", "island__sucursal__name")
    inlines = [NozzleInline]


@admin.register(Nozzle)
class NozzleAdmin(admin.ModelAdmin):
    list_display = ("number", "machine", "fuel_numeral", "fuel_type")
    list_filter = ("machine__island__sucursal", "fuel_type")
    search_fields = ("number", "machine__island__sucursal__name")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("code", "sucursal", "description", "start_time", "end_time", "manager")
    list_filter = ("sucursal",)
    search_fields = (
        "code",
        "description",
        "sucursal__name",
        "manager__user_FK__username",
    )


@admin.register(ServiceSession)
class ServiceSessionAdmin(admin.ModelAdmin):
    list_display = ("shift", "started_at", "initial_budget", "close_mode")
    list_filter = ("shift__sucursal", "started_at", "close_mode")
    search_fields = ("shift__code", "shift__sucursal__name")
    date_hierarchy = "started_at"
    filter_horizontal = ("attendants",)


@admin.register(ServiceSessionFuelLoad)
class ServiceSessionFuelLoadAdmin(admin.ModelAdmin):
    list_display = (
        "service_session",
        "inventory",
        "liters_added",
        "invoice_number",
        "date",
    )
    list_filter = (
        "inventory__sucursal",
        "inventory__fuel_type",
        "date",
    )
    search_fields = (
        "invoice_number",
        "driver_name",
        "license_plate",
    )
@admin.register(ServiceSessionProductLoad)
class ServiceSessionProductLoadAdmin(admin.ModelAdmin):
    list_display = (
        "service_session",
        "product",
        "quantity_added",
        "date",
    )
    list_filter = (
        "product__sucursal",
        "product__product_type",
        "date",
    )
    search_fields = (
        "product__product_type",
        "product__batch_number",
    )


class ServiceSessionProductSaleItemInline(admin.TabularInline):
    model = ServiceSessionProductSaleItem
    extra = 0


@admin.register(ServiceSessionProductSale)
class ServiceSessionProductSaleAdmin(admin.ModelAdmin):
    list_display = (
        "service_session",
        "sold_at",
        "responsible",
    )
    list_filter = (
        "service_session__shift__sucursal",
        "sold_at",
    )
    search_fields = (
        "service_session__shift__code",
        "responsible__user_FK__username",
        "items__product__product_type",
    )
    date_hierarchy = "sold_at"
    inlines = [ServiceSessionProductSaleItemInline]


@admin.register(ServiceSessionCreditSale)
class ServiceSessionCreditSaleAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer_name",
        "service_session",
        "fuel_inventory",
        "amount",
        "responsible",
        "created_at",
    )
    list_filter = (
        "service_session__shift__sucursal",
        "fuel_inventory__fuel_type",
        "created_at",
    )
    search_fields = (
        "invoice_number",
        "customer_name",
        "responsible__user_FK__username",
    )
    date_hierarchy = "created_at"


@admin.register(ServiceSessionTransbankVoucher)
class ServiceSessionTransbankVoucherAdmin(admin.ModelAdmin):
    list_display = (
        "service_session",
        "total_amount",
        "responsible",
        "registered_at",
    )
    list_filter = ("service_session__shift__sucursal", "registered_at")
    search_fields = (
        "service_session__shift__code",
        "responsible__user_FK__username",
        "responsible__user_FK__first_name",
        "responsible__user_FK__last_name",
    )
    date_hierarchy = "registered_at"


@admin.register(ServiceSessionFirefighterPayment)
class ServiceSessionFirefighterPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "service_session",
        "firefighter",
        "amount",
        "registered_at",
    )
    list_filter = ("service_session__shift__sucursal", "registered_at")
    search_fields = (
        "service_session__shift__code",
        "firefighter__user_FK__username",
        "firefighter__user_FK__first_name",
        "firefighter__user_FK__last_name",
    )
    date_hierarchy = "registered_at"