# pactool

[한국어](README.ko.md) | **English**

A small, dependency-free Python tool for inspecting, verifying, unpacking and repacking
**Unisoc / Spreadtrum PAC firmware files** (`.pac`, format `BP_R1.0.0`), the format used by
ResearchDownload / SPD Flash Tool.

- No extra packages: a single file that runs on Python 3.8+ (Windows, macOS, Linux)
- Recomputes file offsets and both header CRCs (CRC-16/ARC) when repacking
- Records the original layout in `manifest.json` so a PAC can be rebuilt in the same order

> **Disclaimer**
> Flashing firmware can make a device unusable and may void its warranty. This tool only
> rebuilds the PAC container; it does not make modified images valid for your device.
> You use it entirely at your own risk. Only use it on devices you own.

---

## Requirements

- Python 3.8 or newer
- Enough free disk space: unpacking needs about the size of the PAC, and repacking needs
  about the same again (a 4 GB PAC needs roughly 8 GB free)

## Usage

```
python pactool.py info    <firmware.pac>
python pactool.py verify  <firmware.pac>
python pactool.py unpack  <firmware.pac> <folder>
python pactool.py repack  <folder> <new.pac>
python pactool.py replace <firmware.pac> <FileID> <new_file> <new.pac>
```

| Command | What it does |
|---|---|
| `info` | Prints the PAC format, product, firmware name and the list of files (ID, file name, size). |
| `verify` | Checks the header CRC and the data CRC. Exits with code 0 when both are valid, 1 otherwise. |
| `unpack` | Extracts every file into a folder and writes `manifest.json` describing the original layout. |
| `repack` | Rebuilds a PAC from an unpacked folder, using `manifest.json` for order and metadata. |
| `replace` | Builds a new PAC with one file swapped out, without unpacking everything first. |

### Examples

Show the contents of a PAC:
```
python pactool.py info firmware.pac
```

Check that a PAC is intact before doing anything else:
```
python pactool.py verify firmware.pac
```

Replace one file (for example `NV_LTE`) and write a new PAC:
```
python pactool.py replace firmware.pac NV_LTE my_nvitem.bin firmware_new.pac
python pactool.py verify firmware_new.pac
```

Unpack, edit, and repack:
```
python pactool.py unpack firmware.pac work
# replace files inside "work" (keep the same file names)
python pactool.py repack work firmware_new.pac
python pactool.py verify firmware_new.pac
```

Unpacked files are named `NN_<FileID>__<original name>` (for example `07_NV_LTE__sharkl5pro_pubcp_customer_nvitem.bin`)
so that entries with the same original name (such as two `logo.bmp` files) do not collide.
When repacking, overwrite the file under the same name; do not rename it.

File IDs are the names shown in ResearchDownload's file list (`BOOT`, `VBMETA`, `NV_LTE`,
`Modem_LTE`, …). Run `info` to see the IDs in your PAC.

## Recommended check for a new device

pactool has only been tested on a few PAC files (see below). Before relying on it for a
different device, run these three steps on that device's original PAC:

1. `python pactool.py info firmware.pac` lists the files correctly.
2. `python pactool.py verify firmware.pac` reports both CRCs as valid.
3. Unpack and repack without changing anything, then compare the result with the original:
   - Windows: `fc /b firmware.pac firmware_repacked.pac`
   - macOS / Linux: `cmp firmware.pac firmware_repacked.pac`

If all three pass, pactool reads that PAC layout correctly.

## Tested

| Device | PAC format | unpack → repack identical | same-size replace |
|---|---|---|---|
| Teclast T40 Pro (ID: T1A1) | BP_R1.0.0 | Yes | Yes |
| Teclast P50 (ID: G5C1), Android 14, EEA firmware | BP_R1.0.0 | Yes | Yes |

## Limitations

- Only the `BP_R1.0.0` PAC format is supported. Other versions (for example `BP_R2.x`) are
  rejected with an error instead of being processed incorrectly.
- Replacing a file with one of a **different size** is implemented but has not been fully
  verified. Always run `verify` on the result.
- pactool does not check partition size limits. A file larger than its partition will
  produce a PAC that fails during flashing.
- pactool does not modify or re-sign images. Files whose names end in `-sign` (FDL, SPL,
  U-Boot, TrustOS, etc.) are protected by the device's secure boot; a PAC containing a
  modified version will usually not boot.
- CRC calculation is written in pure Python, so verifying or repacking a multi-gigabyte PAC
  takes several minutes. Progress is shown in the console.

## What this repository does not contain

This repository contains only the tool's source code. It does **not** include any firmware
files, extracted images, or signing keys, and none should be added. Firmware belongs to the
device and chip manufacturers.

## License

MIT License. See `LICENSE`.
