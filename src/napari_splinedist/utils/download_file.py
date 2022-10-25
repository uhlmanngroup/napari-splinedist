import requests


def download_file(url, path, status_callback, chunk_size=4096):
    """download a file from an url and save it to a path.

        we implement this as a generator, since this allows
        us to cancel the download. This is particular usefull
        when this function is run in a worker thread.

    Parameters
    ----------
    url : TYPE
        Description
    path : TYPE
        Description
    status_callback : TYPE
        Description
    chunk_size : int, optional
        Description

    Yields
    ------
    TYPE
        Description
    """
    chunks = []

    response = requests.get(url, stream=True)
    total_length = response.headers.get("content-length")

    if total_length is None:  # no content length header
        chunks.append(response.content)
    else:
        dl = 0
        total_length = int(total_length)
        status_callback(0, total_length, dl)
        for data in response.iter_content(chunk_size=chunk_size):
            dl += len(data)
            chunks.append(data)
            percent = 100.0 * dl / total_length
            status_callback(percent, total_length, dl)

            yield

    with open(path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)
