from django.contrib import admin
from .models import Simulation, RastreioAudit


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display  = ('id', 'lote', 'name', 'total', 'created_by', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('lote', 'name', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(RastreioAudit)
class RastreioAuditAdmin(admin.ModelAdmin):
    list_display  = ('id', 'created_at', 'acao', 'nunota', 'sequencia',
                     'codagregacao', 'qtd', 'nomeusu')
    list_filter   = ('acao', 'created_at')
    search_fields = ('nunota', 'codagregacao', 'nomeusu')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
