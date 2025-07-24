from django.contrib import admin
from .models import Asset, NetWorthSnapshot

admin.site.register(Asset)
admin.site.register(NetWorthSnapshot)
