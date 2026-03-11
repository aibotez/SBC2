from rest_framework import serializers
from .models import FileNode
class FileNodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = FileNode
        fields = [
            "parent_id",
            "name",
            "is_dir",
            # "parent",
            "size",
            "sha256",
            "created_at",
            'mtime'
            # "updated_at"
        ]

    # class Meta:
    #     model = FileNode
    #     fields = "__all__"


# class UploadSerializer(serializers.Serializer):
#     parent_id = serializers.IntegerField(required=False, allow_null=True)

class ListSerializer(serializers.Serializer):

    parent_id = serializers.IntegerField(required=False, allow_null=True)
    path = serializers.CharField(required=False, allow_blank=True)

class MkdirSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    path = serializers.CharField(required=False, allow_blank=True)