# pactool

**한국어** | [English](README.md)

**Unisoc / Spreadtrum PAC 펌웨어 파일**(`.pac`, `BP_R1.0.0` 형식)을 살펴보고, 검사하고,
풀고, 다시 묶는 파이썬 도구입니다. ResearchDownload / SPD Flash Tool에서 쓰는 형식을 다룹니다.

- 추가 설치 없이 파일 하나로 동작합니다 (Python 3.8 이상, 윈도우·맥·리눅스)
- 다시 묶을 때 파일 위치(오프셋)와 헤더 CRC 두 개(CRC-16/ARC)를 자동으로 다시 계산합니다
- 원래 구조를 `manifest.json`에 기록해서, 같은 순서로 pac를 다시 만들 수 있습니다

> **면책 조항**
>
> 펌웨어 플래싱은 기기를 사용할 수 없게 만들 수 있고, 제조사 보증이 무효가 될 수 있습니다.
> 이 도구는 pac 파일의 겉포장만 다시 만들 뿐, 수정한 이미지가 기기에서 정상 동작하도록 해 주지 않습니다.
> 사용에 따른 모든 책임은 사용자에게 있습니다. 본인 소유 기기에만 사용하세요.

---

## 필요한 것

- Python 3.8 이상
- 충분한 저장 공간: 풀 때 pac 크기만큼, 다시 묶을 때 또 그만큼 필요합니다
  (4GB pac라면 약 8GB 여유 공간)

## 사용법

```
python pactool.py info    <펌웨어.pac>
python pactool.py verify  <펌웨어.pac>
python pactool.py unpack  <펌웨어.pac> <폴더>
python pactool.py repack  <폴더> <새파일.pac>
python pactool.py replace <펌웨어.pac> <파일ID> <바꿀파일> <새파일.pac>
```

| 명령 | 하는 일 |
|---|---|
| `info` | pac 형식, 제품명, 펌웨어 이름, 들어 있는 파일 목록(ID, 파일명, 크기)을 보여 줍니다. |
| `verify` | 헤더 CRC와 데이터 CRC를 검사합니다. 둘 다 정상이면 종료 코드 0, 아니면 1을 돌려줍니다. |
| `unpack` | 모든 파일을 폴더에 풀고, 원래 구조를 `manifest.json`에 기록합니다. |
| `repack` | 풀어 둔 폴더를 `manifest.json`의 순서와 정보대로 다시 묶습니다. |
| `replace` | 전체를 풀지 않고 파일 하나만 바꿔 새 pac를 만듭니다. |

### 예시

pac 안의 파일 목록 보기:
```
python pactool.py info firmware.pac
```

작업 전에 pac가 손상되지 않았는지 확인하기:
```
python pactool.py verify firmware.pac
```

파일 하나(예: `NV_LTE`)를 바꿔 새 pac 만들기:
```
python pactool.py replace firmware.pac NV_LTE my_nvitem.bin firmware_new.pac
python pactool.py verify firmware_new.pac
```

풀어서 수정한 뒤 다시 묶기:
```
python pactool.py unpack firmware.pac work
# "work" 폴더 안의 파일을 같은 이름으로 덮어쓰기
python pactool.py repack work firmware_new.pac
python pactool.py verify firmware_new.pac
```

풀린 파일 이름은 `번호_<파일ID>__<원래이름>` 형식입니다
(예: `07_NV_LTE__sharkl5pro_pubcp_customer_nvitem.bin`).
원래 이름이 같은 항목(예: `logo.bmp` 두 개)이 서로 덮어쓰지 않게 하려는 것입니다.
다시 묶을 때는 **같은 이름 그대로** 파일을 덮어쓰고, 이름을 바꾸지 마세요.

파일 ID는 ResearchDownload 파일 목록에 나오는 이름입니다(`BOOT`, `VBMETA`, `NV_LTE`,
`Modem_LTE` 등). 내 pac에 어떤 ID가 있는지는 `info`로 확인할 수 있습니다.

## 새 기기에서 처음 쓸 때 권장하는 확인

pactool은 아래 "시험한 기기"에 적힌 pac로만 시험했습니다. 다른 기기에 쓰기 전에,
그 기기의 원본 pac로 다음 세 단계를 확인하세요.

1. `python pactool.py info firmware.pac`에서 파일 목록이 정상적으로 나오는지
2. `python pactool.py verify firmware.pac`에서 CRC 두 개가 모두 정상인지
3. 아무것도 바꾸지 않고 풀었다가 다시 묶은 결과가 원본과 똑같은지
   - 윈도우: `fc /b firmware.pac firmware_repacked.pac`
   - 맥 / 리눅스: `cmp firmware.pac firmware_repacked.pac`

세 단계를 모두 통과하면 pactool이 그 pac 구조를 제대로 읽고 있다는 뜻입니다.

## 시험한 기기

| 기기 | pac 형식 | 풀기 → 다시 묶기 동일 | 같은 크기 파일 교체 |
|---|---|---|---|
| Teclast T40 Pro (ID: T1A1) | BP_R1.0.0 | 예 | 예 |
| Teclast P50 (ID: G5C1), Android 14, EEA 펌웨어 | BP_R1.0.0 | 예 | 예 |

## 한계

- `BP_R1.0.0` 형식만 지원합니다. 다른 버전(예: `BP_R2.x`)은 잘못 처리하지 않고 오류를 내며 멈춥니다.
- **크기가 다른 파일**로 바꾸는 기능은 구현돼 있지만 검증을 끝내지 못했습니다. 결과물은 꼭 `verify`로 확인하세요.
- 파티션 크기 한도는 검사하지 않습니다. 파티션보다 큰 파일을 넣으면 플래싱 단계에서 실패합니다.
- 이미지를 수정하거나 다시 서명하지 않습니다. 이름이 `-sign`으로 끝나는 파일(FDL, SPL, U-Boot,
  TrustOS 등)은 기기의 보안 부팅으로 보호되므로, 수정본을 넣은 pac는 대부분 부팅되지 않습니다.
- CRC 계산을 순수 파이썬으로 하기 때문에, 수 GB짜리 pac를 검사하거나 다시 묶는 데 몇 분이 걸립니다.
  진행률은 콘솔에 표시됩니다.

## 이 저장소에 포함되지 않는 것

이 저장소에는 도구의 소스 코드만 들어 있습니다. 펌웨어 파일, 추출한 이미지, 서명 키는
**포함하지 않으며, 추가해서도 안 됩니다.** 펌웨어의 권리는 기기 제조사와 칩 제조사에 있습니다.

## 라이선스

MIT 라이선스. `LICENSE` 파일을 참고하세요.
