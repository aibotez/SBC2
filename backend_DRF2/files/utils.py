

import os
from django.conf import settings
from .models import FileNode



def get_user_root(user):

    path = os.path.join(
        settings.DATA_ROOT,
        'user',
        user.username
    )

    os.makedirs(path, exist_ok=True)

    return path
def build_real_path(node):
    parts = []
    cur = node
    while cur.parent:
        parts.append(cur.name)
        cur = cur.parent
    parts.append(cur.name)
    parts.reverse()
    user_root = os.path.join(
        settings.DATA_ROOT,
        'user',
        node.owner.username
    )
    return os.path.join(user_root, *parts)
def get_node_by_path(user, path):
    path = path.strip("/")
    if not path:
        return None   # 根目录
    parts = path.split("/")
    parent = None
    for name in parts:
        node = FileNode.objects.filter(
            owner=user,
            parent=parent,
            name=name,
            is_dir=True
        ).first()
        if not node:
            raise Exception("path not found")
        parent = node
    return parent