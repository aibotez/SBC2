from django.shortcuts import render

# Create your views here.


from rest_framework import viewsets, permissions
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import FileRecord
from .serializers import FileListSerializer, FileCreateSerializer
from rest_framework.decorators import action
from .models import FileRecord, UploadSession
import os,shutil
from django.conf import settings
from django.core.files.base import ContentFile


def get_folder_relative_path(folder_obj):
    """
    根据文件夹对象递归生成相对路径字符串
    例如：folder_obj(plasma_data) -> "experiment/plasma_data"
    """
    parts = []
    curr = folder_obj
    while curr:
        parts.insert(0, curr.name)
        curr = curr.parent_folder
    return os.path.join(*parts) if parts else ""

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
        # 1. 解析参数
        file_md5 = request.data.get('file_md5')
        file_name = request.data.get('file_name')

        path_str = request.data.get('path')  # 脚本传: "experiment/plasma_data"

        # --- [2. 路径转对象逻辑] ---
        # 这个 parent_obj 就是数据库里的“文件夹记录”
        parent_obj = None
        if path_str:
            # 逐级解析路径，确保每一层文件夹都存在
            parts = [p for p in path_str.strip('/').split('/') if p]
            current_parent = None
            for part in parts:
                # 这里的 get_or_create 会自动产生 parent_id
                folder_obj, created = FileRecord.objects.get_or_create(
                    user=request.user,
                    name=part,
                    parent_folder=current_parent,
                    is_folder=True,
                    defaults={'size': 0}
                )
                current_parent = folder_obj
            parent_obj = current_parent  # 最终解析出来的文件夹对象


        try:
            total_size = int(request.data.get('total_size', 0))
            offset = int(request.data.get('offset', 0))
        except (ValueError, TypeError):
            return Response({"error": "参数格式错误"}, status=400)



        # --- 【核心逻辑：三重检查秒传】 ---

        # 检查点 1：完全相同（路径相同 + MD5 相同） -> 什么都不做
        exact_match = FileRecord.objects.filter(
            user=request.user,
            name=file_name,
            parent_folder=parent_obj,
            file_md5=file_md5,
            is_folder=False
        ).first()

        if exact_match and os.path.exists(exact_match.physical_path):
            return Response({
                "status": "success",
                "msg": "文件已存在，无需重复上传",
                "file_id": exact_match.id,
                "instant": True  # 标记为完全幂等跳过
            })

        # 检查点 2：MD5 相同但路径不同 -> 物理拷贝秒传
        existing_file = FileRecord.objects.filter(file_md5=file_md5, is_folder=False).first()

        if existing_file and os.path.exists(existing_file.physical_path):
            # A. 处理同名冲突：如果当前路径下已有“同名但 MD5 不同”的文件，清理它
            # 注意：上方的检查点 1 已经排除了 MD5 相同的情况
            old_record = FileRecord.objects.filter(
                user=request.user, name=file_name, parent_folder=parent_obj, is_folder=False
            ).first()
            if old_record:
                if old_record.physical_path and os.path.exists(old_record.physical_path):
                    os.remove(old_record.physical_path)
                old_record.delete()

            # B. 执行物理拷贝秒传

            relative_dir = os.path.join('data', request.user.username,path_str)
            abs_dir = os.path.join(settings.BASE_DIR, relative_dir)
            os.makedirs(abs_dir, exist_ok=True)
            new_physical_path = os.path.join(abs_dir, file_name)

            try:
                shutil.copy2(existing_file.physical_path, new_physical_path)
                new_record = FileRecord.objects.create(
                    user=request.user,
                    name=file_name,
                    parent_folder=parent_obj,
                    is_folder=False,
                    file_md5=file_md5,
                    size=existing_file.size,
                    file_obj=os.path.relpath(new_physical_path, settings.MEDIA_ROOT),
                    physical_path=new_physical_path
                )
                return Response({"status": "success", "msg": "秒传成功（副本已物理就绪）", "file_id": new_record.id})
            except Exception as e:
                print(f"物理拷贝失败: {e}")

        # --- 【常规逻辑：分片上传】 ---

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "缺少分片文件"}, status=400)

        # 维护上传会话
        session, created = UploadSession.objects.get_or_create(
            file_md5=file_md5,
            defaults={'total_size': total_size, 'user': request.user, 'file_name': file_name}
        )

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{file_md5}.part")

        mode = 'rb+' if os.path.exists(temp_path) else 'wb'
        with open(temp_path, mode) as f:
            f.seek(offset)
            f.write(file_obj.read())

        session.received_size += file_obj.size
        session.save()

        # 检查合并
        if session.received_size >= total_size:
            # 最后的清理逻辑保持不变...
            # (删除同名异 MD5 记录, 创建新记录, 移动文件, 清理 temp)
            old_record = FileRecord.objects.filter(
                user=request.user, name=file_name, parent_folder=parent_obj, is_folder=False
            ).first()
            if old_record:
                if old_record.physical_path and os.path.exists(old_record.physical_path):
                    os.remove(old_record.physical_path)
                old_record.delete()

            new_record = FileRecord.objects.create(
                user=request.user,
                name=file_name,
                parent_folder=parent_obj,
                is_folder=False,
                file_md5=file_md5,
                size=total_size
            )

            with open(temp_path, 'rb') as f:
                new_record.file_obj.save(file_name, ContentFile(f.read()), save=True)

            new_record.physical_path = new_record.file_obj.path
            new_record.save()

            session.delete()
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return Response({"status": "success", "msg": "上传完成"})

        return Response({
            "status": "uploading",
            "received": session.received_size,
            "progress": round((session.received_size / total_size) * 100, 2)
        })