#!/usr/bin/env python3
"""
pactool.py - Unisoc/Spreadtrum PAC firmware unpacker / repacker (BP_R1.0.0)

명령:
  python pactool.py info    <firmware.pac>
  python pactool.py unpack  <firmware.pac> <폴더>
  python pactool.py repack  <폴더> <새파일.pac>
  python pactool.py replace <firmware.pac> <파일ID> <새파일> <새파일.pac>
  python pactool.py verify  <firmware.pac>

- unpack: 모든 파일을 폴더에 풀고, 원래 구조를 manifest.json에 기록합니다.
- repack: manifest.json 순서대로 다시 묶습니다. 폴더 안의 파일을 바꿔 넣으면
  크기가 달라도 오프셋과 헤더 CRC를 자동으로 다시 계산합니다.
- replace: 풀지 않고 파일 하나(예: NV_LTE, BOOT, VBMETA)만 바꿔 새 pac를 만듭니다.
- verify: 헤더 CRC와 데이터 CRC를 검사합니다.

추가 설치 없이 Python 3.8 이상에서 동작합니다.
"""
import json
import os
import struct
import sys
import time

HDR_SIZE = 2124          # BP_R1.0.0 header
ENTRY_SIZE = 2580        # per-file entry
MAGIC = 0xFFFAFFFA
CHUNK = 8 << 20

# ---------------------------------------------------------------- CRC-16/ARC
_T = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _T.append(_c)
_T = tuple(_T)


def crc16(data, crc=0):
    t = _T
    for b in data:
        crc = (crc >> 8) ^ t[(crc ^ b) & 0xFF]
    return crc


class Progress:
    def __init__(self, total, label):
        self.total, self.label, self.done, self.t0, self.last = total, label, 0, time.time(), 0

    def add(self, n):
        self.done += n
        now = time.time()
        if now - self.last > 1 or self.done >= self.total:
            self.last = now
            pct = 100.0 * self.done / max(1, self.total)
            sys.stdout.write(f"\r  {self.label}: {pct:5.1f}% ({self.done >> 20}/{self.total >> 20} MB)")
            sys.stdout.flush()
            if self.done >= self.total:
                sys.stdout.write(f"  [{now - self.t0:.0f}s]\n")


# ---------------------------------------------------------------- parsing
def wstr(b):
    return b.decode("utf-16le", "ignore").split("\x00")[0]


def wenc(s, nbytes):
    raw = s.encode("utf-16le")
    if len(raw) > nbytes - 2:
        raise ValueError(f"string too long: {s}")
    return raw + b"\x00" * (nbytes - len(raw))


def read_header(f):
    f.seek(0)
    h = f.read(HDR_SIZE)
    if len(h) < HDR_SIZE:
        raise ValueError("파일이 너무 작습니다")
    version = wstr(h[0:44])
    if not version.startswith("BP_R1"):
        raise ValueError(f"지원하지 않는 pac 형식입니다: {version!r} (BP_R1.0.0만 지원)")
    magic, crc1, crc2 = struct.unpack("<IHH", h[2116:2124])
    if magic != MAGIC:
        raise ValueError("pac 헤더 매직값이 다릅니다")
    count, start = struct.unpack("<II", h[1076:1084])
    return {
        "raw": h,
        "version": version,
        "product": wstr(h[52:564]),
        "firmware": wstr(h[564:1076]),
        "count": count,
        "start": start,
        "crc1": crc1,
        "crc2": crc2,
    }


def read_entries(f, hdr):
    f.seek(hdr["start"])
    out = []
    for i in range(hdr["count"]):
        e = f.read(ENTRY_SIZE)
        hs, ho, ls, flag, chk, lo, omit, addrn = struct.unpack("<8I", e[1532:1564])
        out.append({
            "index": i,
            "raw": e,
            "id": wstr(e[4:516]),
            "name": wstr(e[516:1028]),
            "size": (hs << 32) | ls,
            "offset": (ho << 32) | lo,
        })
    return out


def patch_entry(raw, size, offset):
    e = bytearray(raw)
    hs, ho, ls, flag, chk, lo, omit, addrn = struct.unpack("<8I", e[1532:1564])
    e[1532:1564] = struct.pack("<8I", size >> 32, offset >> 32, size & 0xFFFFFFFF,
                               flag, chk, offset & 0xFFFFFFFF, omit, addrn)
    return bytes(e)


def safe_filename(idx, ent):
    base = ent["name"] or "noname"
    base = "".join(c if c.isalnum() or c in "._-+" else "_" for c in base)
    fid = "".join(c if c.isalnum() or c in "._-" else "_" for c in ent["id"]) or "XML"
    return f"{idx:02d}_{fid}__{base}"


def copy_stream(src, dst, n, prog=None, crc=None):
    while n:
        b = src.read(min(n, CHUNK))
        if not b:
            raise IOError("파일이 예상보다 짧습니다")
        dst.write(b)
        if crc is not None:
            crc[0] = crc16(b, crc[0])
        if prog:
            prog.add(len(b))
        n -= len(b)


# ---------------------------------------------------------------- commands
def cmd_info(pac):
    with open(pac, "rb") as f:
        h = read_header(f)
        ents = read_entries(f, h)
    print(f"형식     : {h['version']}")
    print(f"제품     : {h['product']}")
    print(f"펌웨어   : {h['firmware']}")
    print(f"파일 수  : {h['count']}")
    print(f"{'#':>3} {'ID':<22}{'파일명':<52}{'크기':>12}")
    for e in ents:
        print(f"{e['index']:>3} {e['id']:<22}{e['name']:<52}{e['size']:>12}")


def cmd_verify(pac):
    with open(pac, "rb") as f:
        h = read_header(f)
        ok1 = crc16(h["raw"][:2120]) == h["crc1"]
        size = os.path.getsize(pac)
        f.seek(HDR_SIZE)
        c = [0]
        prog = Progress(size - HDR_SIZE, "데이터 CRC 계산")
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            c[0] = crc16(b, c[0])
            prog.add(len(b))
    ok2 = c[0] == h["crc2"]
    print(f"헤더 CRC : {'정상' if ok1 else '불일치'}")
    print(f"데이터 CRC: {'정상' if ok2 else '불일치'} (저장값 0x{h['crc2']:04x}, 계산값 0x{c[0]:04x})")
    return ok1 and ok2


def cmd_unpack(pac, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(pac, "rb") as f:
        h = read_header(f)
        ents = read_entries(f, h)
        total = sum(e["size"] for e in ents)
        prog = Progress(total, "풀기")
        manifest = {
            "tool": "pactool",
            "header_hex": h["raw"].hex(),
            "entries": [],
        }
        for e in ents:
            item = {"index": e["index"], "id": e["id"], "name": e["name"],
                    "orig_size": e["size"], "entry_hex": e["raw"].hex(), "file": None}
            if e["size"]:
                fn = safe_filename(e["index"], e)
                item["file"] = fn
                with open(os.path.join(outdir, fn), "wb") as o:
                    f.seek(e["offset"])
                    copy_stream(f, o, e["size"], prog)
            manifest["entries"].append(item)
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as m:
        json.dump(manifest, m, ensure_ascii=False, indent=1)
    print(f"완료: {outdir} (manifest.json 포함)")


def _write_pac(out_path, header_raw, items):
    """items: list of (entry_raw, size, opener) where opener() -> file object or None."""
    count = len(items)
    start = HDR_SIZE
    data_off = start + count * ENTRY_SIZE
    entries = []
    off = data_off
    for raw, size, _ in items:
        entries.append(patch_entry(raw, size, off if size else 0))
        off += size
    h = bytearray(header_raw)
    h[1076:1084] = struct.pack("<II", count, start)
    total_size = off
    h[44:52] = struct.pack("<II", total_size >> 32, total_size & 0xFFFFFFFF)
    crc = [0]
    prog = Progress(total_size - HDR_SIZE, "묶기")
    tmp = out_path + ".part"
    with open(tmp, "wb") as o:
        o.write(b"\x00" * HDR_SIZE)
        for e in entries:
            o.write(e)
            crc[0] = crc16(e, crc[0])
        prog.add(len(entries) * ENTRY_SIZE)
        for raw, size, opener in items:
            if not size:
                continue
            with opener() as src:
                copy_stream(src, o, size, prog, crc)
        c1 = crc16(bytes(h[:2116]) + struct.pack("<I", MAGIC))
        h[2116:2124] = struct.pack("<IHH", MAGIC, c1, crc[0])
        o.seek(0)
        o.write(h)
    if os.path.exists(out_path):
        os.remove(out_path)
    os.rename(tmp, out_path)
    print(f"완료: {out_path} (헤더 CRC 0x{c1:04x}, 데이터 CRC 0x{crc[0]:04x})")


def cmd_repack(indir, out_path):
    with open(os.path.join(indir, "manifest.json"), encoding="utf-8") as m:
        man = json.load(m)
    items = []
    for it in man["entries"]:
        raw = bytes.fromhex(it["entry_hex"])
        if it["file"]:
            p = os.path.join(indir, it["file"])
            size = os.path.getsize(p)
            if size != it["orig_size"]:
                print(f"  변경됨: {it['id'] or it['name']} {it['orig_size']} -> {size} bytes")
            items.append((raw, size, (lambda p=p: open(p, "rb"))))
        else:
            items.append((raw, 0, None))
    _write_pac(out_path, bytes.fromhex(man["header_hex"]), items)


def cmd_replace(pac, file_id, newfile, out_path):
    with open(pac, "rb") as f:
        h = read_header(f)
        ents = read_entries(f, h)
    match = [e for e in ents if e["id"] == file_id]
    if not match:
        ids = ", ".join(e["id"] for e in ents if e["id"])
        sys.exit(f"ID '{file_id}'를 찾을 수 없습니다. 가능한 ID: {ids}")
    if os.path.abspath(pac) == os.path.abspath(out_path):
        sys.exit("출력 파일은 원본과 다른 이름이어야 합니다.")
    items = []
    for e in ents:
        if e["id"] == file_id:
            size = os.path.getsize(newfile)
            print(f"  교체: {file_id} ({e['name']}) {e['size']} -> {size} bytes")
            items.append((e["raw"], size, (lambda p=newfile: open(p, "rb"))))
        elif e["size"]:
            def opener(off=e["offset"]):
                fh = open(pac, "rb")
                fh.seek(off)
                return fh
            items.append((e["raw"], e["size"], opener))
        else:
            items.append((e["raw"], 0, None))
    _write_pac(out_path, h["raw"], items)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, a = argv[1], argv[2:]
    try:
        if cmd == "info" and len(a) == 1:
            cmd_info(a[0])
        elif cmd == "verify" and len(a) == 1:
            sys.exit(0 if cmd_verify(a[0]) else 1)
        elif cmd == "unpack" and len(a) == 2:
            cmd_unpack(a[0], a[1])
        elif cmd == "repack" and len(a) == 2:
            cmd_repack(a[0], a[1])
        elif cmd == "replace" and len(a) == 4:
            cmd_replace(*a)
        else:
            print(__doc__)
            sys.exit(2)
    except (ValueError, IOError) as e:
        sys.exit(f"오류: {e}")


if __name__ == "__main__":
    main(sys.argv)
