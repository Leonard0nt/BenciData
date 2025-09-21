from django.contrib import admin
from homeApp.models import Company
# Register your models here.

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("business_name", "rut", "profile")