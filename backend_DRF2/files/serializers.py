from rest_framework import serializers
from .models import FileNode
class FileNodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = FileNode
        fields = "__all__"


class UploadSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField(required=False, allow_null=True)