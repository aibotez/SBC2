from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import FileRecord

@admin.register(FileRecord)
class FileRecordAdmin(admin.ModelAdmin):
    # 后台列表页显示的字段
    list_display = ('name', 'user', 'is_folder', 'parent_folder', 'share_type', 'created_at')
    # 过滤器（侧边栏）
    list_filter = ('is_folder', 'share_type', 'user')
    # 搜索框
    search_fields = ('name',)
