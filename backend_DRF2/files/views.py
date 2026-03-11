from django.shortcuts import render

# Create your views here.

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import FileNode
from .serializers import FileNodeSerializer


import os
import hashlib
import shutil

from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import FileNode, UploadSession


from .utils import build_real_path
from .storage import link_or_copy
from .utils import get_node_by_path,get_node





def getnode(request,post=None,get=None):
    path = None
    if get:
        datas=request.GET
    elif post:
        datas = request.POST

    parent_id = None
    if 'parent_id' in datas:
        parent_id = int(datas.get('parent_id'))
    elif 'path'in request.GET:
        path = datas.get("path", "/")
    else:
        path = '/'
    parent = get_node(request.user, path=path,parent_id=parent_id)
    return parent

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_file(request):
    sha256 = request.data["sha256"]
    size = request.data["size"]
    mtime = int(request.data["mtime"])
    filename = request.data["filename"]
    path = request.data.get("path", "/")
    # print(path,66)

    parent = get_node_by_path(request.user, path)
    if parent==-1:
        return JsonResponse({
            "error": 'path error!'
        })
    node = FileNode.objects.filter(
        sha256=sha256,
        size=size
    ).first()
    if node:
        user_dir = os.path.join(
            settings.DATA_ROOT,
            'user',
            request.user.username
        )
        os.makedirs(user_dir, exist_ok=True)
        src = build_real_path(node)

        # 目标目录
        if parent:
            dst_dir = build_real_path(parent)
        else:
            dst_dir = os.path.join(
                settings.DATA_ROOT,
                "user",
                request.user.username
            )
        dst = os.path.join(dst_dir, filename)
        mode = link_or_copy(src, dst)
        if mode == 'same':
            return JsonResponse({
                "instant": True,
                "mode": mode
            })
        os.utime(dst, (mtime, mtime))
        FileNode.objects.update_or_create(
            name=filename,
            parent=parent,
            owner=request.user,
            size=size,
            mtime=mtime,
            sha256=sha256
        )
        return JsonResponse({
            "instant": True,
            "mode": mode
        })
    # cach = FileNode.objects.filter(sha256=sha256,file_size=size).first()
    # if cach:
    session = UploadSession.objects.filter(
        owner=request.user,
        parent=parent,
        name=filename,
        size=size,
        sha256=sha256
    ).first()

    if session:
        return JsonResponse({
            "upload_id": session.upload_id,
            "offset": session.uploaded
        })

    return JsonResponse({
        "instant": False
    })
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_upload(request):
    import uuid
    upload_id = uuid.uuid4().hex
    temp_path = os.path.join(
        settings.DATA_ROOT,
        "temp",
        str(upload_id)
    )

    filename = request.data["filename"]
    size = int(request.data["size"])
    sha256 = request.data["sha256"]
    path = request.data.get("path", "/")
    parent = get_node_by_path(request.user, path)
    chunk_size = int(request.data["chunk_size"])
    total_chunks = (size + chunk_size - 1) // chunk_size
    session = UploadSession.objects.create(
        owner=request.user,
        name=filename,
        size=size,
        sha256=sha256,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        parent=parent,
        upload_id=upload_id,
        temp_path=temp_path,
    )

    return JsonResponse({
        "upload_id": str(upload_id),
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "offset": 0
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_chunk(request):
    upload_id = request.data["upload_id"]
    # chunk_index = int(request.data["chunk_index"])
    offset = int(request.POST["offset"])
    # file = request.FILES["chunk"]
    chunk = request.FILES["file"]
    session = UploadSession.objects.get(upload_id=upload_id)

    temp_path = os.path.join(settings.DATA_ROOT,"temp")
    if not os.path.isdir(temp_path):
        os.makedirs(temp_path)

    with open(session.temp_path, "a+b") as f:
        f.seek(offset)
        for c in chunk.chunks():
            f.write(c)

    session.uploaded = offset + chunk.size
    session.save(update_fields=["uploaded"])

    return JsonResponse({
        "offset": session.uploaded
    })


    # temp_dir = os.path.join(
    #     settings.DATA_ROOT,
    #     "temp",
    #     str(upload_id)
    # )
    # os.makedirs(temp_dir, exist_ok=True)
    # chunk_path = os.path.join(
    #     temp_dir,
    #     str(chunk_index)
    # )
    # with open(chunk_path, "wb") as f:
    #     for c in file.chunks():
    #         f.write(c)
    # uploaded = session.uploaded_chunks
    # uploaded.append(chunk_index)
    # session.uploaded_chunks = uploaded
    # session.save()
    # return JsonResponse({"ok": True})



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def finish_upload(request):
    upload_id = request.data["upload_id"]
    mtime = int(request.data["mtime"])
    session = UploadSession.objects.get(upload_id=upload_id)
    # print(session)
    final_path = build_real_path(session)

    shutil.move(session.temp_path, final_path)


    user_dir = os.path.join(
        settings.DATA_ROOT,
        'user',
        request.user.username
    )

    path = final_path.replace(user_dir,'').replace(session.name,'').replace('\\','/')
    # print(path)
    parent = get_node_by_path(request.user, path)
    # temp_dir = os.path.join(
    #     settings.DATA_ROOT,
    #     "temp",
    #     str(upload_id)
    # )
    # user_dir = os.path.join(
    #     settings.DATA_ROOT,
    #     'user',
    #     request.user.username
    # )
    # os.makedirs(user_dir, exist_ok=True)
    # final_path = os.path.join(
    #     user_dir,
    #     session.filename
    # )
    # with open(final_path, "wb") as outfile:
    #     for i in range(session.total_chunks):
    #         chunk_path = os.path.join(temp_dir, str(i))
    #         with open(chunk_path, "rb") as infile:
    #             shutil.copyfileobj(infile, outfile)
    os.utime(final_path, (mtime, mtime))


    FileNode.objects.create(
        name=session.name,
        owner=request.user,
        size=session.size,
        sha256=session.sha256,
        mtime=mtime,
        is_dir=False,
        parent=parent,
    )
    # shutil.rmtree(session.temp_path)
    session.delete()
    return JsonResponse({"success": True})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def upload_status(request):
    upload_id = request.GET.get("upload_id")
    session = UploadSession.objects.get(id=upload_id)
    uploaded = session.uploaded_chunks or []
    return JsonResponse({
        "uploaded_chunks": uploaded
    })




@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mkdir(request):

    path = request.data.get("path", "/")
    name = request.data.get("name")

    if not name:
        return JsonResponse({"error": "name required"}, status=400)

    parent = get_node_by_path(request.user, path)

    # 防止重复
    exists = FileNode.objects.filter(
        owner=request.user,
        parent=parent,
        name=name,
        is_dir=True
    ).exists()
    if exists:
        return JsonResponse({"error": "folder exists"}, status=400)
    # ---------- 新增物理目录 ----------
    disk_path = os.path.join(
        settings.DATA_ROOT,
        'user',
        request.user.username,
        path.strip("/"),
        name
    )
    os.makedirs(disk_path, exist_ok=True)

    stat = os.stat(disk_path)
    mtime = int(stat.st_mtime)


    node = FileNode.objects.create(
        owner=request.user,
        parent=parent,
        name=name,
        mtime=mtime,
        is_dir=True
    )

    return JsonResponse({
        "id": node.id,
        "name": node.name
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_files(request):
    # parent_id = None
    # if 'parent_id' in request.GET:
    #     parent_id = request.GET.get('parent_id')
    # elif 'path'in request.GET:
    #     path = request.GET.get("path", "/")
    # else:
    #     path = '/'
    # parent = get_node(request.user, path=path,parent_id=parent_id)

    parent = getnode(request, get=1)
    if parent==-1:
        return JsonResponse({"error": "path not found"}, status=400)

    nodes = FileNode.objects.filter(
        owner=request.user,
        parent=parent
    )
    folders = []
    files = []
    for n in nodes:
        item = {
            # "id": n.id,
            "name": n.name,
            "mtime":n.mtime,
            'parent_id':n.parent_id
        }
        if n.is_dir:
            folders.append(item)
        else:
            item["size"] = n.size
            item["sha256"] = n.sha256
            files.append(item)
    return JsonResponse({
        # "path": path,
        "folders": folders,
        "files": files,

    })
class FileNodeViewSet(viewsets.ModelViewSet):
    serializer_class = FileNodeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FileNode.objects.filter(owner=self.request.user)
