from rest_framework.routers import DefaultRouter
from .views import FileNodeViewSet
from django.urls import path
from .views import (
    check_file,
    create_upload,
    upload_chunk,
    finish_upload,
    upload_status
)


router = DefaultRouter()
router.register("files", FileNodeViewSet, basename="files")

urlpatterns = [
    path("upload/check/", check_file),
    path("upload/create/", create_upload),
    path("upload/chunk/", upload_chunk),
    path("upload/finish/", finish_upload),
    path("upload/status/", upload_status),
]
urlpatterns += router.urls