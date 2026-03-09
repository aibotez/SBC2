from rest_framework import serializers
from .models import FileNode


class FileNodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = FileNode
        fields = "__all__"