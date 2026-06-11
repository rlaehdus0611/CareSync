"""
헬스케어 AI 오케스트레이터
입력 하나로 식단 / 운동 / 멘탈 에이전트를 라우팅하고 통합 응답 반환
"""
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from router import classify_intent

# ── 에이전트 URL 설정 ────────────────────────────────────────────────
AGENT_URLS = {
    "mental":   os.getenv("MENTAL_AGENT_URL",   "http://localhost:8000"),
    "diet":     os.getenv("DIET_AGENT_URL",     "http://localhost:8001"),
    "exercise": os.getenv("EXERCISE_AGENT_URL", "http://localhost:8002"),
}

# ── 에이전트별 요청 엔드포인트 & 페이로드 키 ────────────────────────
AGENT_ENDPOINTS = {
    "mental":   "/journal",
    "diet":     "/diet",
    "exercise": "/exercise",
}
AGENT_PAYLOAD_KEY = {
    "mental":   "content",
    "diet":     "content",
    "exercise": "content",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="헬스케어 AI 오케스트레이터", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


def _short_text(text: str, limit: int = 95) -> str:
    text = " ".join(str(text or "").split())
    return text[:limit] + "..." if len(text) > limit else text


def _clean_generated_text(text: str) -> str:
    """Remove accidental non-Korean CJK glyphs that local LLMs sometimes mix into Korean."""
    text = str(text or "").replace("`", "")
    text = re.sub(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF]+", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.!?。！？])", r"\1", text)
    return text.strip()


def _sanitize_agent_payload(value):
    if isinstance(value, str):
        return _clean_generated_text(value)
    if isinstance(value, list):
        return [_sanitize_agent_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_agent_payload(item) for key, item in value.items()}
    return value


def _mental_signal_label(signal: dict | None) -> str:
    if not signal:
        return "멘탈 상태 정보 없음"
    emotion = signal.get("primary_emotion") or signal.get("primary") or "감정"
    intensity = signal.get("intensity")
    care = "주의 필요" if signal.get("requires_care") else "일반 관리"
    return f"{emotion} / 강도 {intensity}/10 / {care}" if intensity else f"{emotion} / {care}"


def _build_synthesis(results: list["AgentResult"]) -> str:
    ok = {r.agent: r.response for r in results if r.status == "ok" and r.response}
    parts = []
    if "mental" in ok:
        signal = ok["mental"].get("agent_signal")
        parts.append(f"멘탈 상태는 {_mental_signal_label(signal)}로 확인했어요.")
    if "diet" in ok:
        parts.append("식단 쪽에서는 폭식/식사 입력을 기준으로 무리한 제한보다 회복 가능한 식사 방향을 우선했어요.")
    if "exercise" in ok:
        exercise_signal = ok["exercise"].get("agent_signal", {})
        intensity = exercise_signal.get("intensity") or ok["exercise"].get("intensity")
        parts.append(f"운동 쪽에서는 현재 상태에 맞춰 {intensity or '가벼운'} 강도의 활동을 권장했어요.")
    if len(ok) >= 2:
        parts.append("그래서 최종 답변은 식단 조절과 가벼운 움직임을 함께 제안하는 방향으로 정리했어요.")
    return "\n".join(f"- {part}" for part in parts) if parts else "응답 가능한 에이전트 결과가 없어 최종 종합을 만들지 못했어요."


def _dialogue_mental_to_diet(signal: dict | None) -> str:
    emotion_note = _mental_signal_label(signal)
    return (
        f"멘탈: 현재 감정 신호는 {emotion_note}예요. "
        "식단 쪽에서는 오늘을 벌주는 제한식보다 속이 편하고 회복 가능한 식사 방향으로 봐주세요."
    )


def _dialogue_mental_to_exercise(signal: dict | None) -> str:
    emotion_note = _mental_signal_label(signal)
    return (
        f"멘탈: 현재 감정 신호는 {emotion_note}예요. "
        "운동 쪽에서는 강하게 몰아붙이기보다 산책, 스트레칭처럼 긴장을 낮추는 루틴으로 맞춰주세요."
    )


def _dialogue_diet_to_exercise(diet_context: str | None) -> str:
    context = f" 식단 판단 요약은 '{diet_context}'입니다." if diet_context else ""
    return (
        "식단: 폭식이나 과식 뒤에는 칼로리를 벌충하려는 운동보다 소화와 컨디션 회복이 먼저예요."
        f"{context} 운동 쪽에서 가벼운 움직임으로 이어주세요."
    )


def _build_synthesis_dialogue(results: list["AgentResult"]) -> str:
    ok = {r.agent: r.response for r in results if r.status == "ok" and r.response}
    lines = []
    if "mental" in ok:
        lines.append(f"멘탈: 감정 상태는 {_mental_signal_label(ok['mental'].get('agent_signal'))}로 확인했어요.")
    if "diet" in ok:
        lines.append("식단: 그래서 식사는 자책성 제한보다 속이 편한 회복 식사로 정리하는 게 좋아 보여요.")
    if "exercise" in ok:
        exercise_signal = ok["exercise"].get("agent_signal", {})
        intensity = exercise_signal.get("intensity") or ok["exercise"].get("intensity") or "low"
        lines.append(f"운동: 현재 상태에는 {intensity} 강도의 가벼운 움직임을 우선 추천할게요.")
    if len(ok) >= 2:
        lines.append("오케스트레이터: 세 의견을 합쳐 식단 조절과 가벼운 움직임을 함께 제안하는 결론으로 정리했어요.")
    if not lines:
        return "결론 도출 대화\n오케스트레이터: 응답 가능한 에이전트 결과가 없어 최종 종합을 만들지 못했어요."
    return "결론 도출 대화\n" + "\n".join(f"- {line}" for line in lines)


# ── 스키마 ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    force_agent: str | None = None   # "mental" | "diet" | "exercise" | None(자동)
    # 사용자 프로필 정보 추가 (선택 사항)
    age: int | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    goal: str | None = None
    activity_level: str | None = None
    food_style: str | None = None
    restrictions: str | None = None

class AgentResult(BaseModel):
    agent: str
    status: str          # "ok" | "error" | "unavailable"
    response: dict | None = None
    error: str | None = None

class ChatResponse(BaseModel):
    routed_to: list[str]
    reason: str
    results: list[AgentResult]


# ── 에이전트 호출 ────────────────────────────────────────────────────

async def call_agent(agent: str, message: str, user_info: dict | None = None) -> AgentResult:
    url      = AGENT_URLS[agent] + AGENT_ENDPOINTS[agent]
    payload  = {AGENT_PAYLOAD_KEY[agent]: message}

    # 추가 프로필 정보가 있으면 페이로드에 합침 (식단 에이전트 등에서 활용)
    if user_info:
        payload.update(user_info)

    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            return AgentResult(agent=agent, status="ok", response=_sanitize_agent_payload(res.json()))
    except httpx.ConnectError:
        return AgentResult(agent=agent, status="unavailable",
                           error=f"{agent} 에이전트 서버에 연결할 수 없어요.")
    except Exception as e:
        return AgentResult(agent=agent, status="error", error=str(e))


# ── 엔드포인트 ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # 1. 의도 분류 (force_agent 있으면 라우터 스킵)
    if req.force_agent and req.force_agent in AGENT_URLS:
        agents = [req.force_agent]
        reason = f"{req.force_agent} 에이전트 직접 선택"
    else:
        routing = await classify_intent(req.message)
        agents  = routing.get("agents", ["mental"])
        reason  = routing.get("reason", "")

    # 2. 프로필 정보 추출 (제공된 필드만)
    user_info = req.model_dump(exclude={"message", "force_agent"}, exclude_unset=True)

    # 3. 해당 에이전트에 동시 요청
    results = await asyncio.gather(*[
        call_agent(agent, req.message, user_info) for agent in agents
    ])

    return ChatResponse(routed_to=agents, reason=reason, results=list(results))


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    멀티에이전트 대화 과정을 SSE로 실시간 스트리밍
    각 단계마다 이벤트를 보내 UI에서 대화 형태로 보여줌
    """
    AGENT_KO = {"mental": "🧠 멘탈", "diet": "🥗 식단", "exercise": "💪 운동"}

    async def event_generator():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 1. 오케스트레이터 분석 시작
        yield sse("step", {"from": "🤖 오케스트레이터", "msg": "입력을 분석하고 있어요...", "type": "thinking"})
        await asyncio.sleep(0.3)

        # 2. 라우팅 결정
        if req.force_agent and req.force_agent in AGENT_URLS:
            agents = [req.force_agent]
            reason = f"{req.force_agent} 에이전트 직접 선택"
        else:
            routing = await classify_intent(req.message)
            agents  = routing.get("agents", ["mental"])
            reason  = routing.get("reason", "")

        agent_names = ", ".join(AGENT_KO.get(a, a) for a in agents)
        yield sse("step", {"from": "🤖 오케스트레이터", "msg": f"**{agent_names}** 에이전트에게 전달할게요.\n이유: {reason}", "type": "routing"})
        await asyncio.sleep(0.2)

        # 3. 에이전트 순차 호출 — 멘탈 먼저, 결과를 다음 에이전트에 전달
        user_info = req.model_dump(exclude={"message", "force_agent"}, exclude_unset=True)
        results = []
        mental_signal = None  # 멘탈 에이전트의 신호 (다른 에이전트에게 전달)
        diet_context = None

        # 멘탈을 항상 먼저 실행하도록 정렬
        ordered = sorted(agents, key=lambda a: 0 if a == "mental" else 1)

        for agent in ordered:
            label = AGENT_KO.get(agent, agent)
            yield sse("step", {"from": f"{label} 에이전트", "msg": "분석 중이에요...", "type": "thinking", "agent": agent})

            # 핵심: 멘탈 신호를 식단·운동 에이전트에 전달 (이 한 줄이 에이전트 간 대화를 만듦)
            if agent != "mental" and mental_signal:
                user_info["mental_status"] = mental_signal  # ← 교수님이 말씀하신 한 줄
                if agent == "diet":
                    yield sse("step", {
                        "from": "🧠 멘탈 → 🥗 식단",
                        "msg": _dialogue_mental_to_diet(mental_signal),
                        "type": "routing",
                        "agent": "mental"
                    })
                elif agent == "exercise":
                    yield sse("step", {
                        "from": "🧠 멘탈 → 💪 운동",
                        "msg": _dialogue_mental_to_exercise(mental_signal),
                        "type": "routing",
                        "agent": "mental"
                    })
                await asyncio.sleep(0.2)

            if agent == "exercise" and diet_context:
                user_info["diet_context"] = diet_context
                yield sse("step", {
                    "from": "🥗 식단 → 💪 운동",
                    "msg": _dialogue_diet_to_exercise(diet_context),
                    "type": "routing",
                    "agent": "diet"
                })
                await asyncio.sleep(0.2)

            result = await call_agent(agent, req.message, user_info)
            results.append(result)

            if result.status == "ok" and result.response:
                resp = result.response

                # 멘탈 에이전트 신호 추출 → 다음 에이전트에게 전달
                if agent == "mental" and resp.get("agent_signal"):
                    mental_signal = resp["agent_signal"]
                    emotion   = mental_signal.get("primary_emotion", "")
                    intensity = mental_signal.get("intensity", "")
                    # 멘탈 → 다른 에이전트에게 신호 전달 표시
                    if len(ordered) > 1:
                        others = ", ".join(AGENT_KO.get(a, a) for a in ordered if a != "mental")
                        yield sse("step", {
                            "from": "🧠 멘탈 에이전트 → 전달",
                            "msg": f"**{others}** 에이전트에게 감정 신호를 전달해요.\n감정: {emotion} / 강도: {intensity}/10",
                            "type": "routing", "agent": "mental"
                        })
                        await asyncio.sleep(0.2)

                preview = resp.get("response") or resp.get("empathy_response") or "응답 완료"
                if len(preview) > 80:
                    preview = preview[:80] + "..."
                yield sse("step", {"from": f"{label} 에이전트", "msg": preview, "type": "response", "agent": agent})
                if agent == "diet":
                    diet_context = _short_text(resp.get("response") or resp.get("recommendation") or "", 180)
            else:
                yield sse("step", {"from": f"{label} 에이전트", "msg": f"⚠️ {result.error or '응답 없음'}", "type": "error", "agent": agent})

            await asyncio.sleep(0.1)

        # 4. 오케스트레이터 최종 종합
        yield sse("step", {
            "from": "🤖 오케스트레이터",
            "msg": _build_synthesis_dialogue(results),
            "type": "routing",
            "agent": "system"
        })
        await asyncio.sleep(0.2)
        yield sse("step", {"from": "🤖 오케스트레이터", "msg": "모든 에이전트 응답을 종합했어요 ✅", "type": "done"})

        # 5. 최종 결과 전송
        final = {
            "routed_to": agents,
            "reason": reason,
            "results": [r.model_dump() for r in results]
        }
        yield sse("done", final)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/agents/health")
async def agents_health():
    """모든 에이전트 서버 상태 확인."""
    async def ping(agent: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(url + "/agent/status")
            return {"agent": agent, "status": "online"}
        except Exception:
            return {"agent": agent, "status": "offline"}

    results = await asyncio.gather(*[
        ping(a, u) for a, u in AGENT_URLS.items()
    ])
    return {"agents": list(results)}


@app.get("/journals")
async def get_all_journals(limit: int = 20):
    """모든 에이전트로부터 전체 기록 목록을 가져와 병합하여 반환합니다."""
    async def fetch_history(agent: str):
        url = f"{AGENT_URLS[agent]}/journals"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, params={"limit": limit})
                if resp.status_code == 200:
                    entries = resp.json().get("entries", [])
                    for e in entries:
                        e["_agent"] = agent
                    return entries
        except:
            pass
        return []

    # 모든 에이전트로부터 병렬로 데이터 가져오기
    tasks = [fetch_history(agent) for agent in AGENT_URLS.keys()]
    results = await asyncio.gather(*tasks)
    
    # 리스트 병합 및 시간순 정렬
    combined = [item for sublist in results for item in sublist]
    combined.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {"entries": combined[:limit]}

@app.delete("/journals/{agent}/{entry_id}")
async def delete_journal_entry(agent: str, entry_id: int):
    """특정 에이전트의 기록 삭제 라우팅."""
    if agent not in AGENT_URLS:
        return {"status": "error", "message": "유효하지 않은 에이전트입니다."}
    url = f"{AGENT_URLS[agent]}/journals/{entry_id}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.delete(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


@app.get("/trend")
async def get_emotion_trend(days: int = 7):
    """멘탈 에이전트로부터 감정 추이 데이터를 가져와 반환합니다."""
    url = f"{AGENT_URLS['mental']}/trend"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url, params={"days": days})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"days": days, "data": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    # API 명세서에 따라 오케스트레이터는 9000번 포트에서 실행합니다.
    uvicorn.run(app, host="0.0.0.0", port=9000)
