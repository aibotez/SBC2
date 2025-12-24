from django.db import models

# Create your models here.

import uuid
from django.db import models
from django.contrib.auth.models import User


class FileRecord(models.Model):
    # 分享类型枚举
    SHARE_CHOICES = [
        ('private', '私有'),
        ('shared', '家庭共享'),
        ('public', '公开链接'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')

    # 文件/目录基本信息
    name = models.CharField(max_length=255)
    is_folder = models.BooleanField(default=False, db_index=True)

    # 存储路径：相对于 MEDIA_ROOT 的路径，如 "admin/photos/vacation/"
    # 这样方便你以后通过磁盘扫描重建数据库
    relative_path = models.CharField(max_length=1000, help_text="物理文件夹路径")

    # 目录层级结构
    parent_folder = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )

    # 分享控制预留
    share_type = models.CharField(max_length=10, choices=SHARE_CHOICES, default='private', db_index=True)

    size = models.BigIntegerField(default=0)
    extension = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'parent_folder']),
        ]

    def __str__(self):
        return self.name
