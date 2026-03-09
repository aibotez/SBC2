from django.db import models

# Create your models here.

import uuid,os
from django.db import models
from django.contrib.auth.models import User



def user_directory_path(instance, filename):
    # instance 是当前的 FileRecord 实例
    # 文件将上传到 MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.user.id}/{filename}'
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

    # 增加 MD5 字段
    # 长度 64 位足以兼容 MD5 或 SHA256
    file_md5 = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    # 物理路径（多个记录可以指向同一个物理路径实现秒传）
    physical_path = models.CharField(max_length=500, blank=True, null=True)
    file_obj = models.FileField(upload_to=user_directory_path, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'parent_folder']),
            models.Index(fields=['file_md5']),  # 显式建立 MD5 索引
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 自动提取扩展名
        if not self.is_folder and self.name:
            self.extension = os.path.splitext(self.name)[1].lower().replace('.', '')

        # 自动生成逻辑路径（用于灾备重建）
        if self.parent_folder:
            self.relative_path = os.path.join(self.parent_folder.relative_path, self.name)
        else:
            self.relative_path = self.name  # 根目录

        super().save(*args, **kwargs)


class UploadSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # 文件的唯一标识（前端计算 MD5），用于秒传和断点识别
    file_md5 = models.CharField(max_length=64, db_index=True)

    # 临时存放分片的文件路径（建议放在 /tmp/ 或指定的缓存目录）
    temp_path = models.CharField(max_length=500)

    # 文件原始信息
    file_name = models.CharField(max_length=255)
    total_size = models.BigIntegerField()  # 总字节数
    received_size = models.BigIntegerField(default=0)  # 已接收字节数

    # 记录该文件最终要存放在哪个父目录下
    parent_folder = models.ForeignKey(
        'FileRecord', on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 同一个用户不能同时发起两个相同 MD5 的上传任务
        unique_together = ('user', 'file_md5')
