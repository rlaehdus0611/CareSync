"""
헬스케어 AI 오케스트레이터
입력 하나로 식단 / 운동 / 멘탈 에이전트를 라우팅하고 통합 응답 반환
"""
import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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


# ── 스키마 ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    force_agent: str | None = None   # "mental" | "diet" | "exercise" | None(자동)

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

async def call_agent(agent: str, message: str) -> AgentResult:
    url      = AGENT_URLS[agent] + AGENT_ENDPOINTS[agent]
    payload  = {AGENT_PAYLOAD_KEY[agent]: message}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            return AgentResult(agent=agent, status="ok", response=res.json())
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

    # 2. 해당 에이전트에 동시 요청
    results = await asyncio.gather(*[
        call_agent(agent, req.message) for agent in agents
    ])

    return ChatResponse(routed_to=agents, reason=reason, results=list(results))


@app.get("/agents/health")
async def agents_health():
    """모든 에이전트 서버 상태 확인."""
    async def ping(agent: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
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
    """멘탈 에이전트로부터 전체 일기 목록을 가져와 반환합니다."""
    url = f"{AGENT_URLS['mental']}/journals"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url, params={"limit": limit})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"entries": [], "error": str(e)}


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
