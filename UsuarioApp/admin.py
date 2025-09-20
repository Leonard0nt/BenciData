from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Profile, Position, Statistics

# Register your models here.


class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user_FK",)

    def phone(self, obj):
        return getattr(obj, "phone", "")

admin.site.register(Profile, ProfileAdmin)


class PositionAdmin(admin.ModelAdmin):
    list_display = ("user_position",)


admin.site.register(Position, PositionAdmin)


class StatisticsAdmin(admin.ModelAdmin):
    list_display = ("user", "asistencia", "vacaciones", "permisos")


admin.site.register(Statistics, StatisticsAdmin)
