

# Create your models here.

from django.db import models
from django.contrib.auth.models import User
import uuid


class FileNode(models.Model):

    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    mtime = models.BigIntegerField(null=True)
    is_dir = models.BooleanField(default=False)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True
    )
    extension = models.CharField(
        max_length=10,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [
            models.Index(fields=["owner", "parent"]),
            models.Index(fields=["sha256"]),
        ]

    def __str__(self):
        return self.name


class UploadSession(models.Model):
    # id = models.UUIDField(
    #     primary_key=True,
    #     default=uuid.uuid4,
    #     editable=False
    # )
    # id = models.BigAutoField(primary_key=True)
    parent = models.ForeignKey(
        FileNode,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="upload_sessions",
        # related_name="children"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    size = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    chunk_size = models.IntegerField()
    total_chunks = models.IntegerField()
    uploaded_chunks = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    upload_id = models.CharField(max_length=64, unique=True)
    uploaded = models.BigIntegerField(default=0)
    temp_path = models.CharField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    mtime = models.BigIntegerField(null=True)

