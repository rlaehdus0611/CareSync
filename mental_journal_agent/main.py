"""
멘탈 저널링 에이전트 — FastAPI 서버
"""
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import process_journal
from database import init_db, save_entry, get_entries, get_emotion_trend, get_recent_for_rag, delete_entry
from report_generator import generate_daily_report
from kakao_sender import send_kakao


scheduler = AsyncIOScheduler()

async def _scheduled_report():
    report = await generate_daily_report()
    await send_kakao(report)
    print("[스케줄러] 카카오톡 리포트 전송 완료")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(_scheduled_report, "cron", hour=23, minute=0, misfire_grace_time=600)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="멘탈 저널링 에이전트", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")

if not os.path.exists(static_path):
    os.makedirs(static_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")


# ── 요청/응답 스키마 ──────────────────────────────────────────────

class JournalRequest(BaseModel):
    content: str


class JournalResponse(BaseModel):
    id: int
    emotions: dict
    keywords: list[str]
    empathy_response: str
    agent_signal: dict
    preprocess_method: str


# ── 엔드포인트 ────────────────────────────────────────────────────

@app.get("/")
async def root():
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Mental Agent is running. (index.html missing)"}


@app.post("/journal", response_model=JournalResponse)
async def create_journal(req: JournalRequest):
    """일기 입력 → 감정 분석 + 공감 응답 생성 + 저장."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="일기 내용을 입력해주세요.")

    # RAG: 최근 5개 일기를 컨텍스트로 전달
    past_entries = await get_recent_for_rag(limit=5)
    result = await process_journal(req.content, past_entries=past_entries)

    entry_id = await save_entry(
        content=req.content,
        emotions=result["emotions"],
        empathy_response=result["empathy_response"],
        keywords=result["keywords"],
        intensity=result["emotions"]["intensity"]
    )

    return JournalResponse(id=entry_id, **result)


@app.get("/journals")
async def list_journals(limit: int = 20):
    """저장된 일기 목록 조회."""
    entries = await get_entries(limit=limit)
    return {"entries": entries}


@app.delete("/journals/{entry_id}")
async def remove_journal(entry_id: int):
    """일기 삭제."""
    success = await delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")
    return {"status": "ok"}


@app.get("/trend")
async def emotion_trend(days: int = 7):
    """최근 N일 감정 추이 데이터."""
    data = await get_emotion_trend(days=days)
    return {"days": days, "data": data}


# ── 멀티에이전트 연동 인터페이스 ──────────────────────────────────

@app.get("/agent/status")
async def agent_status():
    """
    다른 에이전트(식단/운동)가 멘탈 상태를 조회하는 엔드포인트.
    최근 일기의 감정 신호를 반환.
    """
    entries = await get_entries(limit=1)
    if not entries:
        return {
            "agent": "mental_journal",
            "status": "ok",
            "sub_status": "no_data",
            "agent_signal": None
        }

    latest = entries[0]
    return {
        "agent": "mental_journal",
        "status": "ok",
        "agent_signal": {
            "agent": "mental_journal",
            "primary_emotion": latest["emotions"]["primary"],
            "intensity": latest["intensity"],
            "requires_care": latest["intensity"] >= 7 and
                             latest["emotions"]["primary"] in ["슬픔", "불안", "분노", "무기력", "외로움"],
            "recorded_at": latest["created_at"]
        }
    }


@app.post("/report/send")
async def send_report():
    """일일 건강 리포트 생성 후 카카오톡으로 전송."""
    report = await generate_daily_report()
    success = await send_kakao(report)
    return {"status": "ok" if success else "error", "report": report}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MENTAL_AGENT_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
