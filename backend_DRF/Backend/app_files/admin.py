from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import UploadSession, FileRecord


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    # 1. 在后台列表页显示的列
    list_display = ('file_name', 'user', 'progress_display', 'file_md5', 'updated_at')

    # 2. 右侧筛选器（按用户和时间过滤）
    list_filter = ('user', 'updated_at')

    # 3. 搜索框（按文件名和 MD5 搜索）
    search_fields = ('file_name', 'file_md5')

    # 4. 自定义一个“进度显示”列，计算百分比
    def progress_display(self, obj):
        if obj.total_size > 0:
            percentage = (obj.received_size / obj.total_size) * 100
            return f"{percentage:.2f}% ({obj.received_size // 1024} KB)"
        return "0%"

    progress_display.short_description = '上传进度'  # 设置后台显示的列名


# 顺便把之前讨论的 FileRecord 也更新一下，加上 MD5
@admin.register(FileRecord)
class FileRecordAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_folder', 'file_md5', 'size', 'created_at')
    list_filter = ('is_folder', 'user')
    search_fields = ('name', 'file_md5')
    # 设置父目录外键的显示方式，方便在后台选择层级
    raw_id_fields = ('parent_folder',)