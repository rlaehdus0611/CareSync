"""
일일 건강 리포트 생성기
멘탈 에이전트 DB + 식단/운동 에이전트 API를 조합해
오늘 하루 건강 요약 리포트를 생성
"""
import os
import json
import httpx
from datetime import datetime, date

import ollama
from database import get_entries, get_emotion_delta

OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
REPORT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

DIET_AGENT_URL     = os.getenv("DIET_AGENT_URL",     "http://localhost:8001")
EXERCISE_AGENT_URL = os.getenv("EXERCISE_AGENT_URL", "http://localhost:8002")

_ollama = ollama.AsyncClient(host=OLLAMA_HOST)

REPORT_SYSTEM = """당신은 헬스케어 AI 코치입니다.
오늘 하루의 멘탈·식단·운동 데이터를 받아 사용자에게 보내는 건강 리포트를 작성하세요.

[형식]
📋 오늘의 건강 리포트 (날짜)

🧠 멘탈
- 오늘의 감정과 변화 요약 (1~2줄)

🥗 식단
- 오늘 식단 상태 요약 (1~2줄, 데이터 없으면 "기록 없음")

💪 운동
- 오늘 운동 상태 요약 (1~2줄, 데이터 없으면 "기록 없음")

✨ 내일을 위한 한마디
- 세 가지 데이터를 종합한 따뜻한 응원 한 줄

[주의]
- 3~4줄 이내로 각 섹션 작성
- 판단하거나 비판하지 말 것
- 자연스러운 한국어, 이모지 포함"""


async def _fetch_agent_status(url: str, agent_name: str) -> dict | None:
    """에이전트 /agent/status 조회. 실패 시 None 반환."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{url}/agent/status")
            if res.status_code == 200:
                return res.json()
    except Exception as e:
        print(f"[리포트] {agent_name} 에이전트 연결 실패: {e}")
    return None


async def collect_today_data() -> dict:
    """오늘 하루 세 에이전트 데이터 수집."""
    today = date.today().isoformat()

    # 멘탈 — 로컬 DB에서 오늘 항목 직접 조회
    all_entries = await get_entries(limit=20)
    today_mental = [e for e in all_entries if e["created_at"].startswith(today)]
    delta = await get_emotion_delta(days=7)

    # 식단·운동 — 에이전트 상태 API 조회
    diet_status     = await _fetch_agent_status(DIET_AGENT_URL,     "식단")
    exercise_status = await _fetch_agent_status(EXERCISE_AGENT_URL, "운동")

    return {
        "date":         today,
        "mental":       today_mental,
        "delta":        delta,
        "diet":         diet_status,
        "exercise":     exercise_status,
    }


def _build_report_prompt(data: dict) -> str:
    """수집 데이터를 LLM 프롬프트용 텍스트로 변환."""
    lines = [f"오늘 날짜: {data['date']}"]

    # 멘탈
    mental_entries = data["mental"]
    if mental_entries:
        emotions = [e["emotions"]["primary"] for e in mental_entries]
        avg_intensity = sum(e["intensity"] for e in mental_entries) / len(mental_entries)
        lines.append(f"\n[멘탈 데이터]")
        lines.append(f"오늘 일기 수: {len(mental_entries)}개")
        lines.append(f"감정 목록: {', '.join(emotions)}")
        lines.append(f"평균 감정 강도: {avg_intensity:.1f}/10")
        delta = data["delta"]
        if delta.get("trend") != "no_data":
            trend_map = {"worsening": "악화 중", "improving": "개선 중", "stable": "안정"}
            lines.append(f"7일 추세: {trend_map.get(delta['trend'], '')} (변화량 {delta.get('delta', 0):+.1f})")
        # 마지막 일기 공감 요약
        if mental_entries:
            lines.append(f"오늘의 핵심 키워드: {', '.join(mental_entries[-1].get('keywords', []))}")
    else:
        lines.append("\n[멘탈 데이터]\n오늘 일기 없음")

    # 식단
    lines.append("\n[식단 데이터]")
    diet = data.get("diet")
    if diet and diet.get("status") == "ok":
        signal = diet.get("agent_signal", {})
        lines.append(f"에이전트 상태: 정상")
        lines.append(f"케어 필요: {'예' if signal.get('requires_care') else '아니오'}")
    else:
        lines.append("식단 에이전트 응답 없음 (오늘 기록 없음)")

    # 운동
    lines.append("\n[운동 데이터]")
    exercise = data.get("exercise")
    if exercise and exercise.get("status") == "ok":
        ex_data = exercise.get("data", {})
        lines.append(f"에이전트 상태: 정상")
        if ex_data.get("intensity"):
            lines.append(f"운동 강도: {ex_data['intensity']}")
    else:
        lines.append("운동 에이전트 응답 없음 (오늘 기록 없음)")

    return "\n".join(lines)


async def generate_daily_report() -> str:
    """일일 리포트 생성 메인 함수."""
    data   = await collect_today_data()
    prompt = _build_report_prompt(data)

    response = await _ollama.chat(
        model=REPORT_MODEL,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        options={"temperature": 0.5},
    )
    return response.message.content.strip()
