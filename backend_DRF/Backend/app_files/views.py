from django.shortcuts import render

# Create your views here.


from rest_framework import viewsets, permissions
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import FileRecord
from .serializers import FileListSerializer, FileCreateSerializer
from rest_framework.decorators import action
from .models import FileRecord, UploadSession
import os
from django.conf import settings
from django.core.files.base import ContentFile

class FileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 依然只看自己的文件
        return FileRecord.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        # 如果是 POST 请求（创建），使用上传专用序列化器
        if self.action == 'create':
            return FileCreateSerializer
        return FileListSerializer

    def perform_create(self, serializer):
        # 1. 从请求数据中获取前端传来的 MD5
        file_md5 = self.request.data.get('file_md5')

        # 2. 尝试在数据库中找一个【物理文件已存在】且【MD5 相同】的记录
        # 这样可以实现“物理去重”，即：多个记录指向同一个磁盘文件
        existing_record = FileRecord.objects.filter(
            file_md5=file_md5
        ).exclude(file_obj='').first()

        if existing_record:
            # 【秒传逻辑】：如果物理文件已存在，直接复用它的 file_obj 路径
            # 这样 Django 就不刻意去写磁盘，也不会生成带随机后缀的新文件
            serializer.save(
                user=self.request.user,
                file_md5=file_md5,  # 显式保存 MD5 到新记录
                file_obj=existing_record.file_obj  # 复用物理路径
            )
        else:
            # 【普通上传】：如果是新 MD5，正常保存文件
            # 记得也要把 file_md5 传进去，否则数据库里这一列永远是空的
            serializer.save(
                user=self.request.user,
                file_md5=file_md5
            )

    @action(detail=False, methods=['post'])
    def upload_chunk(self, request):
        file_md5 = request.data.get('file_md5')
        offset = int(request.data.get('offset'))
        total_size = int(request.data.get('total_size'))
        file_name = request.data.get('file_name')
        file_obj = request.FILES.get('file')

        # 1. 获取会话 (现在由于 import 了，这里不会再报错)
        session, created = UploadSession.objects.get_or_create(
            file_md5=file_md5,
            defaults={'total_size': total_size, 'user': request.user}
        )

        # 2. 写入临时文件 (建议放在 MEDIA_ROOT 下)
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{file_md5}.part")

        # 使用 r+b 模式实现断点续传写入
        mode = 'rb+' if os.path.exists(temp_path) else 'wb'
        with open(temp_path, mode) as f:
            f.seek(offset)
            f.write(file_obj.read())

        # 3. 更新进度并检查是否传完
        session.received_size += file_obj.size
        session.save()

        if session.received_size >= total_size:
            # --- 【关键：转正逻辑】 ---
            with open(temp_path, 'rb') as f:
                # 创建正式的文件记录
                new_record = FileRecord.objects.create(
                    user=request.user,
                    name=file_name,
                    file_md5=file_md5,
                    size=total_size,
                    is_folder=False
                )
                # 关联物理文件（这会自动把文件从 temp 移动到 uploads/%Y/%m/%d/）
                new_record.file_obj.save(file_name, ContentFile(f.read()), save=True)

            # 4. 清理工作
            session.delete()
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return Response({"status": "success", "msg": "文件合并完成"})

        return Response({"status": "uploading", "received": session.received_size})