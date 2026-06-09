"""
카카오톡 "나에게 보내기" 모듈
카카오 REST API를 사용해 본인 카카오톡으로 건강 리포트를 전송
"""
import json
import os
import httpx

KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


async def send_kakao(message: str) -> bool:
    """
    카카오톡 나에게 보내기.
    반환값: 성공 여부 (True/False)
    """
    token = os.getenv("KAKAO_ACCESS_TOKEN")
    if not token:
        print("[카카오] KAKAO_ACCESS_TOKEN 없음 — 전송 스킵")
        return False

    template = json.dumps({
        "object_type": "text",
        "text": message,
        "link": {"web_url": "", "mobile_web_url": ""}
    }, ensure_ascii=False)

    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            KAKAO_SEND_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={"template_object": template},
        )

    if res.status_code == 200 and res.json().get("result_code") == 0:
        print("[카카오] 전송 성공")
        return True
    else:
        print(f"[카카오] 전송 실패: {res.status_code} {res.text}")
        return False
