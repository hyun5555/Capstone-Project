#!/usr/bin/env python
"""
실제 CODEF 응답을 1건씩 받아 저장하고, 응답 "구조"와 정규화 결과를 출력한다.

사용 (backend 폴더에서, 본인 컴퓨터에서 실행):
  # 1) 데모 서버로 먼저 흐름 확인 (요금 없음)
  python scripts/capture_codef.py --env demo --road-name "서울특별시 강남구 테헤란로" --main 152 --sub 0 --address "서울특별시 강남구 테헤란로 152"

  # 2) 실제(운영) 서버로 건축물대장만 1건
  python scripts/capture_codef.py --env prod --only building --road-name "..." --main 100 --sub 0

  # 3) 등기부까지 (운영 서버는 조회 요금이 발생할 수 있어 확인 질문이 나옵니다)
  python scripts/capture_codef.py --env prod --only registry --address "전체 주소"

저장 위치: backend/codef_captures/  (git 에 올라가지 않음 — 원본에 개인정보가 있습니다)
  <시각>_registry_raw.json / building_raw.json   : 원본 (절대 공유·커밋 금지)
  <시각>_registry_masked.json / building_masked.json : 마스킹본 (내용을 눈으로 확인한 뒤 sample_data/ 로 복사해 데모에 사용)

화면에는 값이 아니라 구조(키 이름, 리스트 길이)와 정규화 결과만 나옵니다. 비밀번호/토큰/원본 본문은 출력하지 않습니다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def outline(node, indent: int = 0, key: str = "data", max_depth: int = 6) -> list:
    """값은 보여주지 않고 키/타입/길이만 보여준다."""
    pad = "  " * indent
    if isinstance(node, dict):
        lines = [f"{pad}{key}: {{{len(node)} keys}}"]
        if indent < max_depth:
            for k, v in node.items():
                lines += outline(v, indent + 1, k, max_depth)
        return lines
    if isinstance(node, list):
        lines = [f"{pad}{key}: [{len(node)} items]"]
        if node and indent < max_depth:
            lines += outline(node[0], indent + 1, "[0]", max_depth)
        return lines
    kind = "빈 문자열" if node == "" else type(node).__name__
    return [f"{pad}{key}: <{kind}>"]


def save(path: Path, data: dict) -> None:
    envelope = {"result": {"code": "CF-00000", "message": "captured"}, "data": data}
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize(doc) -> None:
    from app.utils.masking import mask_person_name
    print("  정규화 결과:")
    print(f"    소유자      : {[mask_person_name(n) for n in doc.owner_names] or '(찾지 못함)'}")
    print(f"    용도/구조   : {doc.usage} / {doc.structure}")
    print(f"    전용/연면적 : {doc.area_exclusive} / {doc.area_total}")
    print(f"    준공년도    : {doc.build_year}")
    if doc.doc_type == "registry":
        print(f"    권리(활성)  : {[(r.type, r.amount) for r in doc.active_rights] or '없음'}")
        print(f"    구획 수     : {len(doc.sections)}")
    else:
        print(f"    위반건축물  : {doc.violation}")


async def run(args, client) -> int:
    from app.clients.codef_client import CodefError, fetch_building, fetch_registry
    from app.services.codef_normalizer import normalize_building_response, normalize_registry_response
    from app.utils.masking import mask_building_response, mask_json

    out_dir = BACKEND_DIR / "codef_captures"
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    failed = 0

    if args.only in ("both", "building"):
        print("\n[건축물대장]")
        try:
            data = await fetch_building(client, args.road_name, str(args.main), str(args.sub))
        except CodefError as e:
            print(f"  실패: {e.message} (code={e.code})")
            failed += 1
        else:
            doc = normalize_building_response(data, args.address or args.road_name)
            save(out_dir / f"{stamp}_building_raw.json", data)
            save(out_dir / f"{stamp}_building_masked.json", mask_json(mask_building_response(data), doc.owner_names))
            print("  응답 구조:")
            print("\n".join("    " + line for line in outline(data)))
            summarize(doc)

    if args.only in ("both", "registry"):
        print("\n[등기부등본]")
        proceed = True
        if client.settings.env == "prod" and not args.yes:
            proceed = input("  운영 서버 등기부 조회는 요금이 발생할 수 있습니다. 계속할까요? [y/N] ").strip().lower() == "y"
        if not proceed:
            print("  건너뜀")
        else:
            try:
                data = await fetch_registry(client, args.address)
            except CodefError as e:
                print(f"  실패: {e.message} (code={e.code})")
                failed += 1
            else:
                doc = normalize_registry_response(data, args.address)
                save(out_dir / f"{stamp}_registry_raw.json", data)
                save(out_dir / f"{stamp}_registry_masked.json", mask_json(data, doc.owner_names))
                print("  응답 구조:")
                print("\n".join("    " + line for line in outline(data)))
                summarize(doc)

    print(f"\n저장 폴더: {out_dir}")
    print("※ *_masked.json 을 직접 열어 개인정보가 남아 있지 않은지 확인한 뒤에만 공유하세요. *_raw.json 은 공유 금지.")
    return 1 if failed else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="CODEF 응답 1건 캡처")
    p.add_argument("--env", choices=["demo", "prod"], help="CODEF_ENV 를 덮어쓴다 (기본: .env 값)")
    p.add_argument("--only", choices=["both", "building", "registry"], default="both")
    p.add_argument("--address", default="", help="등기부 조회용 전체 주소")
    p.add_argument("--road-name", default="", help="건축물대장 조회용 도로명")
    p.add_argument("--main", default="", help="본번")
    p.add_argument("--sub", default="0", help="부번")
    p.add_argument("--yes", action="store_true", help="운영 서버 등기부 조회 확인 질문 생략")
    args = p.parse_args(argv)

    if args.env:
        os.environ["CODEF_ENV"] = args.env          # app.config 를 import 하기 전에 설정해야 한다

    if args.only in ("both", "building") and not (args.road_name and args.main):
        p.error("건축물대장 조회에는 --road-name 과 --main 이 필요합니다 (--only registry 로 건너뛸 수 있음)")
    if args.only in ("both", "registry") and not args.address:
        p.error("등기부 조회에는 --address 가 필요합니다 (--only building 으로 건너뛸 수 있음)")

    from app.clients.codef_client import get_codef_client
    client = get_codef_client()
    s = client.settings
    print(f"CODEF 환경: {s.env}  호스트: {s.api_host}")
    missing = [n for n, v in (
        ("CODEF_CLIENT_ID/SECRET(또는 SECOND_*)", s.client_id and s.client_secret),
        ("CODEF_PUBLIC_KEY", s.public_key), ("CODEF_USER_ID", s.user_id), ("CODEF_USER_PW", s.user_pw),
        ("CODEF_PHONE_NO (등기부 조회에 필요)", s.phone_no if args.only != "building" else True),
    ) if not v]
    if missing:
        print("backend/.env 에 없는 값: " + ", ".join(missing))
        return 2
    return asyncio.run(run(args, client))


if __name__ == "__main__":
    sys.exit(main())
