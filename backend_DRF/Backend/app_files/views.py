from django.shortcuts import render

# Create your views here.


from rest_framework import viewsets, permissions
from .models import FileRecord
from .serializers import FileListSerializer


class FileListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    只读视图集，提供文件列表查看功能
    """
    serializer_class = FileListSerializer
    permission_classes = [permissions.IsAuthenticated]  # 必须登录

    def get_queryset(self):
        user = self.request.user
        # 获取查询参数中的父目录 ID
        parent_id = self.request.query_params.get('parent_id')

        # 基础过滤：只能看自己的文件
        queryset = FileRecord.objects.filter(user=user)

        if parent_id:
            # 返回指定目录下的内容
            return queryset.filter(parent_id=parent_id)
        else:
            # 默认返回根目录内容（没有父目录的记录）
            return queryset.filter(parent_folder__isnull=True)