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

class FileCreateSerializer(serializers.ModelSerializer):
    # 将 parent_folder 设为可选项，如果不传则视为根目录
    parent_folder = serializers.PrimaryKeyRelatedField(
        queryset=FileRecord.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = FileRecord
        fields = ['id', 'name', 'is_folder', 'parent_folder', 'file_obj', 'size', 'extension']
        # file_obj 是我们在 Model 里预留的 FileField（如果之前没加，请补上）

    def create(self, validated_data):
        # 自动关联当前登录用户
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)