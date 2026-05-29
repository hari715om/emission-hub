from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    upload_sap, upload_utility, upload_travel,
    IngestionBatchViewSet, SourceRowViewSet,
    UnitMappingViewSet, EmissionFactorViewSet,
)

router = DefaultRouter()
router.register('batches', IngestionBatchViewSet)
router.register('source-rows', SourceRowViewSet)
router.register('unit-mappings', UnitMappingViewSet)
router.register('emission-factors', EmissionFactorViewSet)

urlpatterns = [
    path('ingestion/sap/upload/', upload_sap, name='upload-sap'),
    path('ingestion/utility/upload/', upload_utility, name='upload-utility'),
    path('ingestion/travel/upload/', upload_travel, name='upload-travel'),
    path('', include(router.urls)),
]
