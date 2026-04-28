from django.contrib import admin
from .models import Simulation


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display  = ('id', 'lote', 'name', 'total', 'created_by', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('lote', 'name', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
