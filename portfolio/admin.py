from django.contrib import admin
from .models import Asset, BrazilStock, NetWorthSnapshot

admin.site.register(Asset)
admin.site.register(BrazilStock)

class NetWorthSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'net_worth', 'date', 'created_at')
    fields = ('user', 'net_worth', 'date')

admin.site.register(NetWorthSnapshot, NetWorthSnapshotAdmin)
