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
from django.db import transaction
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
        path_str = request.data.get('path', '').strip('/')  # 脚本传: "experiment/plasma_data"

        try:
            total_size = int(request.data.get('total_size', 0))
            offset = int(request.data.get('offset', 0))
        except (ValueError, TypeError):
            return Response({"error": "参数格式错误"}, status=400)

        # --- [2. 路径转对象逻辑：确保数据库层级存在] ---
        parent_obj = None
        if path_str:
            parts = [p for p in path_str.split('/') if p]
            current_parent = None
            for part in parts:
                # get_or_create 保证幂等性，不会生成重复目录
                folder_obj, _ = FileRecord.objects.get_or_create(
                    user=request.user,
                    name=part,
                    parent_folder=current_parent,
                    is_folder=True
                )
                current_parent = folder_obj
            parent_obj = current_parent

        # --- [3. 三重检查秒传逻辑] ---

        # 检查点 1：完全相同（路径相同 + MD5 相同）
        exact_match = FileRecord.objects.filter(
            user=request.user, name=file_name, parent_folder=parent_obj, file_md5=file_md5, is_folder=False
        ).first()
        if exact_match and os.path.exists(exact_match.physical_path):
            return Response({"status": "success", "msg": "文件已存在", "file_id": exact_match.id, "instant": True})

        # 检查点 2：MD5 相同但路径不同 -> 物理拷贝秒传
        existing_file = FileRecord.objects.filter(file_md5=file_md5, is_folder=False).first()
        if existing_file and os.path.exists(existing_file.physical_path):
            # 构造目标物理路径：data/username/path/filename
            rel_dir = os.path.join('data', request.user.username, path_str)
            abs_dir = os.path.join(settings.BASE_DIR, rel_dir)  # 建议统一基于 MEDIA_ROOT
            os.makedirs(abs_dir, exist_ok=True)
            new_physical_path = os.path.join(abs_dir, file_name)

            # 清理该位置可能存在的“同名但不同MD5”的旧文件
            FileRecord.objects.filter(user=request.user, name=file_name, parent_folder=parent_obj).delete()
            if os.path.exists(new_physical_path):
                os.remove(new_physical_path)

            try:
                shutil.copy2(existing_file.physical_path, new_physical_path)
                new_record = FileRecord.objects.create(
                    user=request.user,
                    name=file_name,
                    parent_folder=parent_obj,
                    is_folder=False,
                    file_md5=file_md5,
                    size=existing_file.size,
                    # 直接更新元数据
                    file_obj=os.path.relpath(new_physical_path, settings.MEDIA_ROOT),
                    physical_path=new_physical_path
                )
                return Response({"status": "success", "msg": "秒传成功", "file_id": new_record.id})
            except Exception as e:
                pass  # 拷贝失败则转入常规上传

        # --- [4. 常规逻辑：分片上传写入临时文件] ---
        file_chunk = request.FILES.get('file')
        if not file_chunk:
            return Response({"error": "缺少分片文件"}, status=400)

        session, _ = UploadSession.objects.get_or_create(
            file_md5=file_md5,
            defaults={'total_size': total_size, 'user': request.user, 'file_name': file_name}
        )

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{file_md5}.part")

        # 内存安全地写入分片
        with open(temp_path, 'a+b' if offset > 0 else 'wb') as f:
            f.seek(offset)
            f.write(file_chunk.read())

        session.received_size += file_chunk.size
        session.save()

        # --- [5. 最终合并：直接重命名 + 元数据登记] ---
        if session.received_size >= total_size:
            # 使用事务保证数据库与物理操作同步
            with transaction.atomic():
                # 1. 清理该路径下的旧同名记录/文件
                old_record = FileRecord.objects.filter(
                    user=request.user, name=file_name, parent_folder=parent_obj, is_folder=False
                ).first()
                if old_record:
                    if old_record.physical_path and os.path.exists(old_record.physical_path):
                        os.remove(old_record.physical_path)
                    old_record.delete()

                # 2. 构造最终存储路径
                rel_dir = os.path.join('data', request.user.username, path_str)
                abs_dir = os.path.join(settings.BASE_DIR, rel_dir)
                os.makedirs(abs_dir, exist_ok=True)
                final_abs_path = os.path.join(abs_dir, file_name)

                # 3. 物理搬家：os.rename 是瞬时完成的，且不占内存
                if os.path.exists(final_abs_path):
                    os.remove(final_abs_path)
                os.rename(temp_path, final_abs_path)

                # 4. 创建数据库记录并直接关联物理路径（不再使用 .save(File) 拷贝数据）
                new_record = FileRecord.objects.create(
                    user=request.user,
                    name=file_name,
                    parent_folder=parent_obj,
                    is_folder=False,
                    file_md5=file_md5,
                    size=total_size,
                    file_obj=os.path.relpath(final_abs_path, settings.MEDIA_ROOT),
                    physical_path=final_abs_path
                )

                session.delete()
                return Response({"status": "success", "msg": "上传并合并完成", "file_id": new_record.id})

        return Response({
            "status": "uploading",
            "received": session.received_size,
            "progress": round((session.received_size / total_size) * 100, 2)
        })