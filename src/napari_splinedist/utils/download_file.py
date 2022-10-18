# import pycurl


# def download_file(url, path, status_callback):
#     def wrapped_cb(download_t, download_d, upload_t, upload_d):
#         progress = 0.0
#         if download_t > 0:

#             progress = 100.0 * download_d / download_t

#         status_callback(progress, download_t, download_d)

#     # download file using pycurl
#     with open(path, "wb") as f:

#         c = pycurl.Curl()
#         c.setopt(c.URL, url)
#         c.setopt(c.WRITEDATA, f)

#         # custom progress bar
#         c.setopt(c.NOPROGRESS, False)
#         c.setopt(c.XFERINFOFUNCTION, wrapped_cb)

#         c.perform()
#         c.close()


import requests


def download_file(url, path, status_callback):
    with open(path, "wb") as f:
        response = requests.get(url, stream=True)
        total_length = response.headers.get("content-length")

        if total_length is None:  # no content length header
            f.write(response.content)
        else:
            dl = 0
            total_length = int(total_length)
            status_callback(0, total_length, dl)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                percent = int(100.0 * dl / total_length)
                status_callback(percent, total_length, dl)
                f.write(data)
