from django.contrib import admin
from .models import Sucursal
# Register your models here.

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "city", "region", "islands")
    search_fields = ("name", "company__business_name", "city", "region")
    list_filter = ("company", "city", "region")
    filter_horizontal = ("users",)