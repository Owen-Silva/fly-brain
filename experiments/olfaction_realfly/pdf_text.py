"""Crude text extraction from a PDF with only the standard library (no PDF package is
installed in the venv). Decompresses every FlateDecode stream and pulls the strings out
of the text-showing operators (Tj, TJ, ' and "). Good enough to grep numbers out of a
paper; not a faithful layout. Usage: python pdf_text.py in.pdf out.txt
"""
import re
import sys
import zlib


def strings_from_content(data: bytes) -> str:
    out = []
    # TJ arrays: [ (abc) -250 (def) ] TJ ; plain: (abc) Tj
    for m in re.finditer(rb"\[(.*?)\]\s*TJ|\((.*?)(?<!\\)\)\s*(?:Tj|'|\")|(T\*|Td|TD|Tm|ET)", data, re.S):
        if m.group(3):
            out.append("\n" if m.group(3) in (b"ET", b"T*") else " ")
            continue
        if m.group(1) is not None:
            parts = re.findall(rb"\((.*?)(?<!\\)\)|(-?\d+\.?\d*)", m.group(1), re.S)
            s = []
            for txt, num in parts:
                if txt:
                    s.append(txt)
                elif num and float(num) < -200:
                    s.append(b" ")
            raw = b"".join(s)
        else:
            raw = m.group(2)
        raw = re.sub(rb"\\([nrtbf()\\])", lambda k: {b"n": b"\n", b"r": b"", b"t": b" ", b"b": b"",
                                                      b"f": b"", b"(": b"(", b")": b")",
                                                      b"\\": b"\\"}[k.group(1)], raw)
        raw = re.sub(rb"\\(\d{3})", lambda k: bytes([int(k.group(1), 8) & 255]), raw)
        out.append(raw.decode("latin-1"))
    return "".join(out)


def main(src, dst):
    pdf = open(src, "rb").read()
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        body = m.group(1)
        try:
            data = zlib.decompress(body)
        except Exception:  # noqa: BLE001
            continue
        if b"BT" in data and (b"Tj" in data or b"TJ" in data):
            texts.append(strings_from_content(data))
    txt = "\n".join(texts)
    open(dst, "w", encoding="utf-8").write(txt)
    print(dst, len(txt), "chars from", len(texts), "text streams")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
