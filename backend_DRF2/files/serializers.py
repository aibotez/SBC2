from rest_framework import serializers
from .models import FileNode
from datetime import datetime
class FileNodeSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    size_str = serializers.SerializerMethodField()
    fileType = serializers.SerializerMethodField()
    class Meta:
        model = FileNode
        fields = [
            "id",
            "parent_id",
            "name",
            "is_dir",
            # "parent",
            "size",
            "sha256",
            "created_at",
            'mtime',
            "date",  # 这里必须加
            "size_str",
            "fileType",
            # "updated_at"
        ]
    def get_date(self, obj):
        if not obj.mtime:
            return None
        return datetime.fromtimestamp(obj.mtime).strftime("%Y-%m-%d")
    def get_size_str(self, obj):
        size = obj.size
        if size is None:
            return None
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"
    def get_fileType(self, obj):
        if obj.is_dir:
            return "folder"
        name = obj.name.lower()
        if name.endswith(".pdf"):
            return "pdf"
        if name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            return "image"
        if name.endswith((".mp4", ".mov", ".avi", ".mkv")):
            return "video"
        if name.endswith((".mp3", ".wav", ".flac")):
            return "audio"
        if name.endswith((".doc", ".docx")):
            return "word"
        if name.endswith((".xls", ".xlsx")):
            return "excel"
        if name.endswith((".ppt", ".pptx")):
            return "ppt"
        return "other"



    # class Meta:
    #     model = FileNode
    #     fields = "__all__"


# class UploadSerializer(serializers.Serializer):
#     parent_id = serializers.IntegerField(required=False, allow_null=True)

class ListSerializer(serializers.Serializer):

    id = serializers.IntegerField(required=False, allow_null=True)
    path = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class MkdirSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    path = serializers.CharField(required=False, allow_blank=True)