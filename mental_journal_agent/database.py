import aiosqlite
from datetime import datetime

DB_PATH = "journal.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                emotions TEXT NOT NULL,         -- JSON: {"primary": "슬픔", "scores": {...}}
                empathy_response TEXT NOT NULL,
                keywords TEXT NOT NULL,          -- JSON: ["외로움", "피곤함", ...]
                intensity INTEGER NOT NULL,      -- 1~10
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def save_entry(content: str, emotions: dict, empathy_response: str,
                     keywords: list[str], intensity: int) -> int:
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO journal_entries
               (content, emotions, empathy_response, keywords, intensity, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content, json.dumps(emotions, ensure_ascii=False),
             empathy_response, json.dumps(keywords, ensure_ascii=False),
             intensity, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_entries(limit: int = 30) -> list[dict]:
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            entry["emotions"] = json.loads(entry["emotions"])
            entry["keywords"] = json.loads(entry["keywords"])
            result.append(entry)
        return result


async def get_recent_for_rag(limit: int = 5) -> list[dict]:
    """RAG용: 최근 N개 일기의 날짜·감정·키워드만 반환 (토큰 절약)."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT created_at, emotions, keywords, intensity
               FROM journal_entries
               ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            entry["emotions"] = json.loads(entry["emotions"])
            entry["keywords"] = json.loads(entry["keywords"])
            result.append(entry)
        return list(reversed(result))  # 시간 순 정렬


async def get_emotion_trend(days: int = 7) -> list[dict]:
    """최근 N일간 날짜별 감정 데이터 반환."""
    import json
    from datetime import timedelta
    from collections import defaultdict

    since = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT date(created_at) as date, emotions, intensity
               FROM journal_entries
               WHERE created_at >= ?
               ORDER BY created_at ASC""",
            (since,)
        )
        rows = await cursor.fetchall()

        # 날짜별로 그룹화하여 데이터 집계
        daily_map = defaultdict(list)
        for row in rows:
            daily_map[row['date']].append(row)

        result = []
        for date_str, entries in daily_map.items():
            avg_intensity = sum(e['intensity'] for e in entries) / len(entries)
            # 해당 날짜의 가장 마지막 일기의 감정을 대표 감정으로 선택
            last_entry_emotions = json.loads(entries[-1]['emotions'])
            result.append({
                "date": date_str,
                "avg_intensity": round(avg_intensity, 1),
                "primary_emotion": last_entry_emotions.get("primary", "평온")
            })
        return result


async def delete_entry(entry_id: int) -> bool:
    """ID를 기반으로 일기 기록 삭제"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        await db.commit()
        return cursor.rowcount > 0
