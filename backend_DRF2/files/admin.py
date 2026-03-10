# from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import FileNode,UploadSession


@admin.register(FileNode)
class FileNodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "is_dir",
        "size",
        "created_at",
        "parent",
        "mtime",
    )

@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "filename",
        "owner",
        "chunk_size",
        "total_chunks",
        "uploaded_chunks",
        "created_at",
        "parent"
    )
