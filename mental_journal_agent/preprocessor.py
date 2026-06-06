"""
한국어 전처리 모듈 — KoNLPy 형태소 분석기
KoNLPy 미설치 시 regex 기반 폴백으로 자동 전환
"""

import os

# Java 17+ 환경에서 네이티브 접근 경고 방지 및 초기화 최적화
jdk_opts = os.environ.get("JDK_JAVA_OPTIONS", "")
if "--enable-native-access=ALL-UNNAMED" not in jdk_opts:
    os.environ["JDK_JAVA_OPTIONS"] = f"{jdk_opts} --enable-native-access=ALL-UNNAMED".strip()

# KNU 한국어 감정 극성 사전 (핵심 단어 subset)
EMOTION_LEXICON = {
    "긍정": ["기쁘", "행복", "즐거", "설레", "뿌듯", "감사", "좋", "사랑", "편안", "홀가분"],
    "부정": ["슬프", "힘들", "지치", "우울", "외롭", "무섭", "불안", "화나", "짜증", "막막",
             "무기력", "허무", "답답", "억울", "후회"],
    "고강도": ["너무", "정말", "완전", "엄청", "매우", "몹시", "굉장히", "극도로"],
}

try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except Exception:
    KONLPY_AVAILABLE = False

_okt_instance = None

def get_okt():
    """Okt 객체를 필요할 때 비로소 생성 (Lazy Initialization)"""
    global _okt_instance
    if _okt_instance is None and KONLPY_AVAILABLE:
        from konlpy.tag import Okt
        _okt_instance = Okt()
    return _okt_instance

def preprocess(text: str) -> dict:
    """
    텍스트 전처리 후 감정 분석 힌트 반환.
    반환 형식:
    {
        "emotion_words": [...],   # 감정 형용사/동사
        "nouns": [...],           # 핵심 명사
        "intensity_hints": [...], # 강도 부사
        "lexicon_signals": {      # 사전 기반 극성 신호
            "positive_count": int,
            "negative_count": int,
            "high_intensity": bool
        }
    }
    """
    if KONLPY_AVAILABLE:
        return _konlpy_preprocess(text)
    return _fallback_preprocess(text)


def _konlpy_preprocess(text: str) -> dict:
    okt = get_okt()
    if not okt:
        return _fallback_preprocess(text)
        
    tokens = okt.pos(text, norm=True, stem=True)

    emotion_words = [w for w, pos in tokens if pos in ("Adjective", "Verb") and len(w) > 1]
    nouns = [w for w, pos in tokens if pos == "Noun" and len(w) > 1]
    adverbs = [w for w, pos in tokens if pos == "Adverb"]

    return {
        "emotion_words": emotion_words[:10],
        "nouns": nouns[:10],
        "intensity_hints": adverbs,
        "lexicon_signals": _lexicon_signals(text),
        "method": "konlpy",
    }


def _fallback_preprocess(text: str) -> dict:
    """KoNLPy 없을 때 간단한 규칙 기반 전처리."""
    import re
    # 조사 제거용 간단 패턴
    words = re.findall(r'[가-힣]{2,}', text)
    return {
        "emotion_words": words[:10],
        "nouns": words[:10],
        "intensity_hints": [w for w in words if w in EMOTION_LEXICON["고강도"]],
        "lexicon_signals": _lexicon_signals(text),
        "method": "fallback",
    }


def _lexicon_signals(text: str) -> dict:
    pos = sum(1 for w in EMOTION_LEXICON["긍정"] if w in text)
    neg = sum(1 for w in EMOTION_LEXICON["부정"] if w in text)
    hi  = any(w in text for w in EMOTION_LEXICON["고강도"])
    return {"positive_count": pos, "negative_count": neg, "high_intensity": hi}


def format_hint(preprocessed: dict) -> str:
    """전처리 결과를 프롬프트 힌트 문자열로 변환."""
    sig = preprocessed["lexicon_signals"]
    lines = []
    if preprocessed["emotion_words"]:
        lines.append(f"감정 관련 어휘: {', '.join(preprocessed['emotion_words'][:6])}")
    if preprocessed["nouns"]:
        lines.append(f"핵심 명사: {', '.join(preprocessed['nouns'][:6])}")
    if preprocessed["intensity_hints"]:
        lines.append(f"강도 부사: {', '.join(preprocessed['intensity_hints'])}")
    lines.append(
        f"어휘 극성: 긍정 신호 {sig['positive_count']}개 / 부정 신호 {sig['negative_count']}개"
        + (" / 고강도 표현 포함" if sig["high_intensity"] else "")
    )
    return "\n".join(lines)
