import os
import math
import hashlib
import requests
from tqdm import tqdm


class CloudClient:

    def __init__(self, server, token, chunk_size=4 * 1024 * 1024):

        self.server = server.rstrip("/") + "/"
        self.chunk_size = chunk_size

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Token {token}"
        })

    # ------------------------
    # 工具函数
    # ------------------------

    def sha256_file(self, path):

        sha = hashlib.sha256()

        with open(path, "rb") as f:
            while True:
                data = f.read(1024 * 1024)
                if not data:
                    break
                sha.update(data)

        return sha.hexdigest()

    # ------------------------
    # 上传接口
    # ------------------------

    def check_instant(self, filename, size, sha256, path):

        url = self.server + "api/upload/check/"

        r = self.session.post(url, json={
            "filename": filename,
            "size": size,
            "sha256": sha256,
            "path": path
        })

        r.raise_for_status()
        print(r.json())

        return r.json()

    def create_upload(self, filename, size, sha256, path):

        total_chunks = math.ceil(size / self.chunk_size)

        url = self.server + "api/upload/create/"

        r = self.session.post(url, json={
            "filename": filename,
            "size": size,
            "chunk_size": self.chunk_size,
            "total_chunks": total_chunks,
            "sha256": sha256,
            "path": path
        })

        r.raise_for_status()

        return r.json()["upload_id"], total_chunks

    def get_uploaded_chunks(self, upload_id):

        url = self.server + "api/upload/status/"

        r = self.session.get(url, params={
            "upload_id": upload_id
        })

        r.raise_for_status()

        return set(r.json()["uploaded_chunks"])

    def upload_chunk(self, upload_id, index, chunk):

        url = self.server + "api/upload/chunk/"

        files = {
            "chunk": chunk
        }

        data = {
            "upload_id": upload_id,
            "chunk_index": index
        }

        r = self.session.post(url, data=data, files=files)

        r.raise_for_status()

    def finish_upload(self, upload_id):

        url = self.server + "api/upload/finish/"

        r = self.session.post(url, json={
            "upload_id": upload_id
        })

        r.raise_for_status()

        return r.json()

    # ------------------------
    # 上传文件
    # ------------------------

    def upload(self, filepath, path="/"):

        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)

        print("calculating sha256...")

        sha256 = self.sha256_file(filepath)

        print("sha256:", sha256)

        # 秒传检测
        res = self.check_instant(filename, size, sha256, path)

        if res.get("instant"):
            print("秒传成功")
            return

        upload_id, total_chunks = self.create_upload(
            filename, size, sha256, path
        )

        print("upload id:", upload_id)

        uploaded = self.get_uploaded_chunks(upload_id)

        with open(filepath, "rb") as f:

            for i in tqdm(range(total_chunks), desc="upload"):

                if i in uploaded:
                    f.seek(self.chunk_size, 1)
                    continue

                chunk = f.read(self.chunk_size)

                self.upload_chunk(upload_id, i, chunk)

        self.finish_upload(upload_id)

        print("upload finished")

    # ------------------------
    # 未来扩展接口
    # ------------------------

    def mkdir(self, path, name):

        url = self.server + "api/files/mkdir/"

        r = self.session.post(url, json={
            "path": path,
            "name": name
        })
        print("status:", r.status_code)
        print("response:", r.text)

        r.raise_for_status()

        return r.json()

    def list_dir(self, path="/"):

        url = self.server + "api/files/"

        r = self.session.get(url, params={
            "path": path
        })

        r.raise_for_status()

        return r.json()

    def download(self, file_id, save_path):

        url = self.server + f"api/files/{file_id}/download/"

        with self.session.get(url, stream=True) as r:

            r.raise_for_status()

            with open(save_path, "wb") as f:

                for chunk in r.iter_content(1024 * 1024):

                    if chunk:
                        f.write(chunk)


# --------------------------------
# 测试
# --------------------------------

if __name__ == "__main__":

    client = CloudClient(
        server="http://127.0.0.1:8000/",
        token="ec8f71c374befa66207ff50f826f8169738d8d81"
    )

    client.upload(
        filepath="D:/网络下载/easytier-linux-arm-v2.4.5.zip",
        path="/test/子目录/123/"      # 指定上传目录
    )

    # client.mkdir(
    #     path='/test/子目录/',
    #     name='123'
    # )