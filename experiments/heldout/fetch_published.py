"""Download the paper's own model output for the grooming figures (Fig. 5, Ext. Data Fig. 4).

Plain English
-------------
Shiu et al. put every simulation result behind their figures in one 4.5 GB zip
file on the Max Planck "Edmond" archive (doi:10.17617/3.CZODIW, MIT licence).
We do not download the whole file. A zip file keeps a table of contents at its
end, so this script asks the server for just the bytes of that table, then for
just the bytes of the few small CSV / pickle files we need. Public data, read
only; nothing is uploaded anywhere.

Output: experiments/heldout/results/published/<path inside the zip>
        experiments/heldout/results/published/_listing.csv (every figure_5 /
        figure_s4 / figure_s5 entry with its size)

Usage:  python experiments/heldout/fetch_published.py [--list-only]
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ARCHIVE = "https://edmond.mpg.de/api/access/datafile/223847"   # results.zip
OUT = Path(__file__).resolve().parent / "results" / "published"
MAX_BYTES = 20_000_000       # never pull a single member bigger than this
WANT_DIRS = ("figure_5/", "figure_s4/", "figure_s5/")


def signed_url():
    """Edmond answers with a redirect to a signed storage URL (valid 24 h)."""
    # A 1-byte GET: the storage server signs GET only (a HEAD gets 403), and
    # its Content-Range header ("bytes 0-0/<total>") gives the file size.
    req = urllib.request.Request(ARCHIVE, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers["Content-Range"].split("/")[-1])
        return r.geturl(), total


class RangeFile(io.RawIOBase):
    """A read-only, seekable file whose bytes come from HTTP range requests."""

    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.n_requests = 0
        self.n_bytes = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        else:
            self.pos = self.size + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        self.n_requests += 1
        self.n_bytes += len(data)
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def main(list_only=False):
    url, size = signed_url()
    print(f"results.zip: {size:,} bytes", flush=True)
    f = io.BufferedReader(RangeFile(url, size), buffer_size=1 << 20)
    z = zipfile.ZipFile(f)
    infos = [i for i in z.infolist() if any(d in i.filename for d in WANT_DIRS)]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = ["filename,compressed_bytes,bytes"]
    for i in infos:
        rows.append(f"{i.filename},{i.compress_size},{i.file_size}")
    (OUT / "_listing.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    small = [i for i in infos if not i.filename.endswith(".parquet")
             and not i.is_dir() and i.file_size <= MAX_BYTES]
    print(f"{len(infos)} entries under {WANT_DIRS}; {len(small)} small non-parquet files", flush=True)
    if list_only:
        for i in small:
            print(f"  {i.filename}  {i.file_size:,}")
        return
    for i in small:
        dest = OUT / i.filename
        if dest.exists() and dest.stat().st_size == i.file_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(i))
        print(f"  got {i.filename} ({i.file_size:,} bytes)", flush=True)


if __name__ == "__main__":
    main(list_only="--list-only" in sys.argv)
