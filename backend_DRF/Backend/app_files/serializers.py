from rest_framework import serializers
from .models import FileRecord

class FileListSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = FileRecord
        fields = ['id', 'name', 'is_folder', 'type', 'size', 'share_type', 'created_at']

    def get_type(self, obj):
        if obj.is_folder:
            return "folder"
        return obj.extension.lower() or "file"