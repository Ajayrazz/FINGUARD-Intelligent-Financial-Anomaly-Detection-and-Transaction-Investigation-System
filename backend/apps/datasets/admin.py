from django.contrib import admin

from .models import ColumnMappingProfile, Dataset, ImportJob, ImportRowError

admin.site.register(Dataset)
admin.site.register(ColumnMappingProfile)
admin.site.register(ImportJob)
admin.site.register(ImportRowError)
