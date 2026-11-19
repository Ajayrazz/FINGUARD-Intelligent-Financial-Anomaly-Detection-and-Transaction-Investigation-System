from django.contrib import admin

from .models import DuplicateCandidate, InvoiceDocument

admin.site.register(InvoiceDocument)
admin.site.register(DuplicateCandidate)
