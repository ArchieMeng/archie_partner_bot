import os
import sys

_srcdir = '%s/you-get/src/' % os.path.dirname(os.path.realpath(__file__))
_filepath = os.path.dirname(sys.argv[0])
sys.path.insert(1, os.path.join(_filepath, _srcdir))

import you_get.common as you_get


def get_info(url):
    result = None
    try:
        result = you_get.any_download(
            url,
            json_output=True
        )
    except Exception as e:
        print(type(e), e)
    return result


def download(url, **kwargs):
    info = get_info(url)
    if isinstance(info, dict):
        title = info['title']
        # Todo fix file too long exception such as URL: https://www.bilibili.com/bangumi/play/ep200459
        you_get.download_main(
            you_get.any_download,
            you_get.any_download_playlist,
            urls=[url],
            playlist=False,
            output_dir='.',
            merge=True,
            **kwargs
        )
    else:
        return info


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=nPVcYFNI0s4"
    info = get_info(url)
    print(info)
    print("file name length:", sys.getsizeof('.'.join((info['title'], info['ext'], 'download', '[00]', '/'))))
    filename, ext = info['title'], info['ext']
    try:
        download(url)
    except OSError as e:
        if str(e.strerror) == "File name too long":
            download(url, output_filename="测试")
    with open('.'.join((filename, ext)), 'rb') as fp:
        fp.seek(0, 2)
        print(fp.tell())