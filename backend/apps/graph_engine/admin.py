from django.contrib import admin

from .models import GraphSnapshot, Neo4jSyncState

admin.site.register(GraphSnapshot)
admin.site.register(Neo4jSyncState)
