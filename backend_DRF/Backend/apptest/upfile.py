import hashlib,os,requests

def calculate_file_md5(file_path):
    """
    分块读取文件并计算 MD5 值
    :param file_path: 文件路径
    :return: 32位 MD5 字符串
    """
    hash_md5 = hashlib.md5()
    # 每次读取 1MB (1024 * 1024 字节)
    chunk_size = 1048576

    with open(file_path, "rb") as f:
        # 循环读取直到文件结束
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()




# 配置
FILE_PATH = "D:/zz/programproject/SBC/fileTMP/test.deb"
CHUNK_SIZE = 1024 * 1024 * 5  # 每片 5MB
BASE_URL = "http://127.0.0.1:8000/api/files/list/" # 注意你的 router 注册名是 list
HEADERS = {"Authorization": "Token dba9832618cf68d2f9ce8787dfba82924af2fe1e"}
# 修改你的上传脚本逻辑
chunk_size = 1024 * 1024 * 10  # 5MB
file_size = os.path.getsize(FILE_PATH)
file_md5 = calculate_file_md5(FILE_PATH)




with open(FILE_PATH, 'rb') as f:
    chunk_index = 0
    while True:
        # 计算当前这块分片的起始位置
        current_offset = chunk_index * chunk_size

        chunk_data = f.read(chunk_size)
        if not chunk_data:
            break

        data = {
            'file_name': os.path.basename(FILE_PATH),
            'file_md5': file_md5,
            'chunk_index': chunk_index,
            'offset': current_offset,  # 👈 必须传这个！
            'total_size': file_size,
            'chunk_size': len(chunk_data)
        }

        files = {'file': chunk_data}

        # 发送请求
        response = requests.post(f"{BASE_URL}upload_chunk/", data=data, files=files, headers=HEADERS)
        # ... 处理响应 ...
        chunk_index += 1
        print(response.text)
    print("✅ 所有分片发送完毕！")

# if __name__ == "__main__":
#     upload_in_chunks()