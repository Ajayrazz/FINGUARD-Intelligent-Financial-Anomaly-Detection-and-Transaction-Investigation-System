from django.contrib import admin

from .models import Alert, AlertPolicy

admin.site.register(Alert)
admin.site.register(AlertPolicy)
