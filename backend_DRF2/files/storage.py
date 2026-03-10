import os
import shutil
import platform


def link_or_copy(src, dst):
    """
    优先使用硬链接，如果失败则copy
    """
    # print(88888,src)
    # print(88888,dst)
    if src == dst:
        # print(88888)
        return 'same'

    os.makedirs(os.path.dirname(dst), exist_ok=True)


    try:
        os.link(src, dst)
        return "link"
    except Exception:

        shutil.copy2(src, dst)
        return "copy"