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

    @action(detail=False, methods=['get'])
    def check_duplicates(self, request):
        """
        找出所有 MD5 相同但路径不同的文件，供用户参考
        """
        from django.db.models import Count
        # 找出重复的 MD5
        duplicate_md5s = FileRecord.objects.values('file_md5') \
            .annotate(total=Count('id')) \
            .filter(total__gt=1, is_folder=False)

        results = []
        for entry in duplicate_md5s:
            files = FileRecord.objects.filter(file_md5=entry['file_md5']).values('id', 'name', 'physical_path', 'size')
            results.append({
                "md5": entry['file_md5'],
                "count": entry['total'],
                "items": list(files)
            })

        return Response(results)
    @action(detail=False, methods=['post'])
    def upload_chunk(self, request):
        # 1. 获取参数（增加防御性判断）
        file_md5 = request.data.get('file_md5') or request.data.get('md5')
        if not file_md5:
            return Response({"error": "缺少 file_md5 参数"}, status=400)

        try:
            offset = int(request.data.get('offset', 0))
            total_size = int(request.data.get('total_size', 0))
        except (ValueError, TypeError):
            return Response({"error": "参数格式错误"}, status=400)

        file_name = request.data.get('file_name')
        file_obj = request.FILES.get('file')

        # 2. 维护上传会话 (追踪进度)
        session, created = UploadSession.objects.get_or_create(
            file_md5=file_md5,
            defaults={
                'total_size': total_size,
                'user': request.user,
                'file_name': file_name
            }
        )

        # 3. 物理写入临时文件
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{file_md5}.part")

        # 使用 rb+ 模式支持随机位置写入，wb 模式用于初始化
        mode = 'rb+' if os.path.exists(temp_path) else 'wb'
        with open(temp_path, mode) as f:
            f.seek(offset)
            f.write(file_obj.read())

        # 4. 更新数据库中的接收进度
        session.received_size += file_obj.size
        session.save()

        print(f"DEBUG: 收到切片大小: {file_obj.size}")
        print(f"DEBUG: 当前总计已接收: {session.received_size} / 预期总大小: {total_size}")

        # 5. 检查是否全部上传完成
        if session.received_size >= total_size:
            # --- 开始合并与转正逻辑 ---

            # A. 处理父目录关联
            parent_id = request.data.get('parent_id')
            parent_folder = None
            if parent_id and str(parent_id).lower() not in ['null', 'undefined', '']:
                parent_folder = FileRecord.objects.filter(
                    id=parent_id,
                    is_folder=True,
                    user=request.user
                ).first()

            # B. 【核心改进】如果存在同名文件，彻底删除旧记录和旧文件
            existing_record = FileRecord.objects.filter(
                user=request.user,
                name=file_name,
                parent_folder=parent_folder,
                is_folder=False
            ).first()

            if existing_record:
                # 删除物理文件
                if existing_record.file_obj and os.path.exists(existing_record.file_obj.path):
                    try:
                        os.remove(existing_record.file_obj.path)
                    except Exception as e:
                        print(f"删除物理文件失败: {e}")
                # 删除数据库记录
                existing_record.delete()

            try:
                # B. 【去重核心】update_or_create
                # 根据 (用户, 父目录, 文件名, 类型) 查找，存在则更新，不存在则创建
                record, created = FileRecord.objects.update_or_create(
                    user=request.user,
                    name=file_name,
                    parent_folder=parent_folder,
                    is_folder=False,
                    defaults={
                        'file_md5': file_md5,
                        'size': total_size,
                    }
                )

                # C. 物理转正：将临时文件内容存入 FileField
                with open(temp_path, 'rb') as f:
                    # save(文件名, 内容) 会自动处理存储路径并生成相对路径存入数据库
                    record.file_obj.save(file_name, ContentFile(f.read()), save=True)

                # D. 补全绝对物理路径
                record.physical_path = record.file_obj.path
                record.save()

                # E. 成功后清理
                session.delete()
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                return Response({
                    "status": "success",
                    "msg": "文件合并完成",
                    "file_id": record.id,
                    "path": record.file_obj.url
                })

            except Exception as e:
                # 如果合并过程中出错，可以选择保留临时文件以便重试，或者清理
                return Response({"status": "error", "msg": f"合并失败: {str(e)}"}, status=500)

        # 6. 未传完，返回当前进度
        return Response({
            "status": "uploading",
            "received": session.received_size,
            "progress": round((session.received_size / total_size) * 100, 2)
        })