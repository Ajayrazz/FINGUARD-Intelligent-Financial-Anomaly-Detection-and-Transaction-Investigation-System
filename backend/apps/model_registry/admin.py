from django.contrib import admin

from .models import MLModel, ModelEvaluation, ModelVersion

admin.site.register(MLModel)
admin.site.register(ModelVersion)
admin.site.register(ModelEvaluation)
