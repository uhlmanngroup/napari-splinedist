import pycurl


def status(progress, total, downloaded):
    if total == 0:
        total = "?"
    print(f"{progress: 0.2f}%  ({downloaded}/{total})")


def download_file(url, path, status_callback):
    def wrapped_cb(download_t, download_d, upload_t, upload_d):
        progress = 0.0
        if download_t > 0:

            progress = 100.0 * download_d / download_t

        status_callback(progress, download_t, download_d)

    # download file using pycurl
    with open(path, "wb") as f:

        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEDATA, f)

        # custom progress bar
        c.setopt(c.NOPROGRESS, False)
        c.setopt(c.XFERINFOFUNCTION, wrapped_cb)

        c.perform()
        c.close()


if __name__ == "__main__":
    url = "https://zenodo.org/record/7194989/files/bbbc038_6.zip?download=1"
    download_file(url, "bubar.zip", status_callback=status)
