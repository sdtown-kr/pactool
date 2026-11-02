#!/usr/bin/env python3
"""
pactool.py - Unisoc/Spreadtrum PAC firmware unpacker / repacker (BP_R1.0.0)

Asks for Korean or English on first run, then shows every message in that
language. Run "python pactool.py help" for usage.

No extra packages needed. Works with Python 3.8 or later.
"""
import json
import locale
import os
import struct
import sys
import time

HDR_SIZE = 2124          # BP_R1.0.0 header
ENTRY_SIZE = 2580        # per-file entry
MAGIC = 0xFFFAFFFA
CHUNK = 8 << 20

# ---------------------------------------------------------------- messages
MESSAGES = {
    "ko": {
        "help": """\
pactool.py - Unisoc/Spreadtrum PAC 펌웨어 풀기/묶기 도구 (BP_R1.0.0)

명령:
  python pactool.py info    <firmware.pac>
  python pactool.py unpack  <firmware.pac> <폴더>
  python pactool.py repack  <폴더> <새파일.pac>
  python pactool.py replace <firmware.pac> <파일ID> <새파일> <새파일.pac>
  python pactool.py verify  <firmware.pac>
  python pactool.py lang    [ko|en]

- unpack: 모든 파일을 폴더에 풀고, 원래 구조를 manifest.json에 기록합니다.
- repack: manifest.json 순서대로 다시 묶습니다. 폴더 안의 파일을 바꿔 넣으면
  크기가 달라도 오프셋과 헤더 CRC를 자동으로 다시 계산합니다.
- replace: 풀지 않고 파일 하나(예: NV_LTE, BOOT, VBMETA)만 바꿔 새 pac를 만듭니다.
- verify: 헤더 CRC와 데이터 CRC를 검사합니다.
- lang: 표시 언어를 바꿉니다. ko나 en을 생략하면 목록에서 고릅니다.

추가 설치 없이 Python 3.8 이상에서 동작합니다.
""",
        "lang_saved": "표시 언어: 한국어 (바꾸려면: python pactool.py lang)",
        "lang_save_failed": "경고: 언어 설정을 저장하지 못했습니다 ({error}). 다음 실행 때 다시 묻습니다.",
        "lang_invalid": "지원하지 않는 언어입니다: {value} (ko 또는 en)",
        "lang_need_choice": "입력을 받을 수 없어 고를 수 없습니다. python pactool.py lang ko 또는 en으로 지정하세요.",
        "error": "오류: {error}",
        "err_string_too_long": "문자열이 너무 깁니다: {value}",
        "err_too_small": "파일이 너무 작습니다",
        "err_unsupported": "지원하지 않는 pac 형식입니다: {version!r} (BP_R1.0.0만 지원)",
        "err_magic": "pac 헤더 매직값이 다릅니다",
        "err_short_file": "파일이 예상보다 짧습니다",
        "err_id_not_found": "ID '{id}'를 찾을 수 없습니다. 가능한 ID: {ids}",
        "err_same_output": "출력 파일은 원본과 다른 이름이어야 합니다.",
        "info_format": "형식     : {value}",
        "info_product": "제품     : {value}",
        "info_firmware": "펌웨어   : {value}",
        "info_count": "파일 수  : {value}",
        "info_header": f"{'#':>3} {'ID':<22}{'파일명':<49}{'크기':>10}",
        "progress_crc": "데이터 CRC 계산",
        "progress_unpack": "풀기",
        "progress_pack": "묶기",
        "crc_ok": "정상",
        "crc_bad": "불일치",
        "verify_header": "헤더 CRC : {status}",
        "verify_data": "데이터 CRC: {status} (저장값 0x{stored:04x}, 계산값 0x{computed:04x})",
        "unpack_done": "완료: {path} (manifest.json 포함)",
        "pack_done": "완료: {path} (헤더 CRC 0x{header:04x}, 데이터 CRC 0x{data:04x})",
        "changed": "  변경됨: {name} {old} -> {new} bytes",
        "replaced": "  교체: {id} ({name}) {old} -> {new} bytes",
    },
    "en": {
        "help": """\
pactool.py - Unisoc/Spreadtrum PAC firmware unpacker / repacker (BP_R1.0.0)

Commands:
  python pactool.py info    <firmware.pac>
  python pactool.py unpack  <firmware.pac> <folder>
  python pactool.py repack  <folder> <new.pac>
  python pactool.py replace <firmware.pac> <file_id> <new_file> <new.pac>
  python pactool.py verify  <firmware.pac>
  python pactool.py lang    [ko|en]

- unpack: extracts every file to the folder and records the original layout
  in manifest.json.
- repack: packs the files back in manifest.json order. If you swap a file in
  the folder, offsets and header CRCs are recalculated even if its size changed.
- replace: makes a new pac with one file changed (e.g. NV_LTE, BOOT, VBMETA)
  without unpacking.
- verify: checks the header CRC and data CRC.
- lang: changes the display language. Without ko or en, shows a list to pick from.

No extra packages needed. Works with Python 3.8 or later.
""",
        "lang_saved": "Language: English (to change: python pactool.py lang)",
        "lang_save_failed": "Warning: could not save the language setting ({error}). You will be asked again next time.",
        "lang_invalid": "Unsupported language: {value} (use ko or en)",
        "lang_need_choice": "Cannot ask for a choice here. Use python pactool.py lang ko or en.",
        "error": "Error: {error}",
        "err_string_too_long": "String too long: {value}",
        "err_too_small": "File is too small",
        "err_unsupported": "Unsupported pac format: {version!r} (only BP_R1.0.0 is supported)",
        "err_magic": "Wrong pac header magic value",
        "err_short_file": "File is shorter than expected",
        "err_id_not_found": "ID '{id}' not found. Available IDs: {ids}",
        "err_same_output": "The output file must have a different name from the original.",
        "info_format": "Format   : {value}",
        "info_product": "Product  : {value}",
        "info_firmware": "Firmware : {value}",
        "info_count": "Files    : {value}",
        "info_header": f"{'#':>3} {'ID':<22}{'File name':<52}{'Size':>12}",
        "progress_crc": "Calculating data CRC",
        "progress_unpack": "Unpacking",
        "progress_pack": "Packing",
        "crc_ok": "OK",
        "crc_bad": "MISMATCH",
        "verify_header": "Header CRC: {status}",
        "verify_data": "Data CRC  : {status} (stored 0x{stored:04x}, calculated 0x{computed:04x})",
        "unpack_done": "Done: {path} (manifest.json included)",
        "pack_done": "Done: {path} (header CRC 0x{header:04x}, data CRC 0x{data:04x})",
        "changed": "  Changed: {name} {old} -> {new} bytes",
        "replaced": "  Replaced: {id} ({name}) {old} -> {new} bytes",
    },
}

# Shown before a language is chosen, so these stay in both languages.
LANGUAGE_MENU = "언어를 선택하세요 / Select a language\n  1. 한국어\n  2. English"
LANGUAGE_INPUT = "번호 입력 / Enter a number (1-2): "
LANGUAGE_RETRY = "1 또는 2를 입력하세요 / Please enter 1 or 2"
LANGUAGE_CHOICES = {
    "1": "ko", "ko": "ko", "kr": "ko", "korean": "ko", "한국어": "ko",
    "2": "en", "en": "en", "eng": "en", "english": "en", "영어": "en",
}

language = "ko"


def tr(key, **values):
    return MESSAGES[language][key].format(**values)


# ---------------------------------------------------------------- language
def setup_console():
    """Keep messages from crashing on consoles that cannot show Korean."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def config_path():
    return os.path.join(os.path.expanduser("~"), ".pactool.json")


def load_language():
    try:
        with open(config_path(), encoding="utf-8") as f:
            code = json.load(f).get("language")
        return code if code in MESSAGES else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def save_language(code):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump({"language": code}, f)
    except OSError as e:
        print(tr("lang_save_failed", error=e), file=sys.stderr)


def system_language():
    try:
        name = locale.getlocale()[0] or ""
    except ValueError:
        name = ""
    return "ko" if name.lower().startswith("ko") else "en"


def can_ask():
    return sys.stdin is not None and sys.stdin.isatty()


def ask_language():
    """Return the chosen language code, or None if input ended."""
    print(LANGUAGE_MENU)
    while True:
        try:
            answer = input(LANGUAGE_INPUT)
        except EOFError:
            print()
            return None
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        code = LANGUAGE_CHOICES.get(answer.strip().lower())
        if code:
            return code
        print(LANGUAGE_RETRY)


def set_language(code):
    global language
    language = code
    save_language(code)
    print(tr("lang_saved"))


def init_language():
    """Use the saved language, asking once if none has been chosen yet."""
    global language
    saved = load_language()
    if saved:
        language = saved
        return
    language = system_language()
    if can_ask():
        code = ask_language()
        if code:
            set_language(code)


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
        raise ValueError(tr("err_string_too_long", value=s))
    return raw + b"\x00" * (nbytes - len(raw))


def read_header(f):
    f.seek(0)
    h = f.read(HDR_SIZE)
    if len(h) < HDR_SIZE:
        raise ValueError(tr("err_too_small"))
    version = wstr(h[0:44])
    if not version.startswith("BP_R1"):
        raise ValueError(tr("err_unsupported", version=version))
    magic, crc1, crc2 = struct.unpack("<IHH", h[2116:2124])
    if magic != MAGIC:
        raise ValueError(tr("err_magic"))
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
            raise IOError(tr("err_short_file"))
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
    print(tr("info_format", value=h["version"]))
    print(tr("info_product", value=h["product"]))
    print(tr("info_firmware", value=h["firmware"]))
    print(tr("info_count", value=h["count"]))
    print(tr("info_header"))
    for e in ents:
        print(f"{e['index']:>3} {e['id']:<22}{e['name']:<52}{e['size']:>12}")


def cmd_verify(pac):
    with open(pac, "rb") as f:
        h = read_header(f)
        ok1 = crc16(h["raw"][:2120]) == h["crc1"]
        size = os.path.getsize(pac)
        f.seek(HDR_SIZE)
        c = [0]
        prog = Progress(size - HDR_SIZE, tr("progress_crc"))
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            c[0] = crc16(b, c[0])
            prog.add(len(b))
    ok2 = c[0] == h["crc2"]
    print(tr("verify_header", status=tr("crc_ok") if ok1 else tr("crc_bad")))
    print(tr("verify_data", status=tr("crc_ok") if ok2 else tr("crc_bad"),
             stored=h["crc2"], computed=c[0]))
    return ok1 and ok2


def cmd_unpack(pac, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(pac, "rb") as f:
        h = read_header(f)
        ents = read_entries(f, h)
        total = sum(e["size"] for e in ents)
        prog = Progress(total, tr("progress_unpack"))
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
    print(tr("unpack_done", path=outdir))


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
    prog = Progress(total_size - HDR_SIZE, tr("progress_pack"))
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
    print(tr("pack_done", path=out_path, header=c1, data=crc[0]))


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
                print(tr("changed", name=it["id"] or it["name"], old=it["orig_size"], new=size))
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
        sys.exit(tr("err_id_not_found", id=file_id, ids=ids))
    if os.path.abspath(pac) == os.path.abspath(out_path):
        sys.exit(tr("err_same_output"))
    items = []
    for e in ents:
        if e["id"] == file_id:
            size = os.path.getsize(newfile)
            print(tr("replaced", id=file_id, name=e["name"], old=e["size"], new=size))
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


def cmd_lang(args):
    global language
    language = load_language() or system_language()
    if len(args) > 1:
        print(tr("help"))
        sys.exit(2)
    if args:
        code = LANGUAGE_CHOICES.get(args[0].strip().lower())
        if not code:
            sys.exit(tr("lang_invalid", value=args[0]))
    elif can_ask():
        code = ask_language()
    else:
        sys.exit(tr("lang_need_choice"))
    if code:
        set_language(code)


def main(argv):
    setup_console()
    if len(argv) >= 2 and argv[1] == "lang":
        cmd_lang(argv[2:])
        return
    init_language()
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(tr("help"))
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
            print(tr("help"))
            sys.exit(2)
    except (ValueError, IOError) as e:
        sys.exit(tr("error", error=e))


if __name__ == "__main__":
    main(sys.argv)
