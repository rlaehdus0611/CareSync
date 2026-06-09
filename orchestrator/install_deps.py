import subprocess
import sys
import os

def install_all():
    # 1. 필수 공통 패키지 목록
    # 각 에이전트 소스 코드를 분석하여 도출된 최소 필요 패키지들입니다.
    common_packages = [
        "fastapi", "uvicorn", "httpx", "python-dotenv", 
        "pydantic", "requests", "aiosqlite", "anthropic", 
        "ollama", "konlpy"
    ]

    print("="*60)
    print("CareSync 프로젝트 통합 의존성 설치를 시작합니다...")
    print("="*60)

    # 가상환경의 pip를 사용하여 설치
    print(f"현재 Python 경로: {sys.executable}")
    
    print("\n[1/2] 공통 패키지 설치 중...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + common_packages)

    # 2. 각 에이전트 폴더 내 requirements.txt가 있다면 추가 설치
    print("\n[2/2] 각 에이전트별 개별 의존성 확인 중...")
    agent_paths = [
        "orchestrator",
        "diet_agent",
        "exercise_agent",
        "mental_journal_agent/mental_journal_agent"
    ]

    for path in agent_paths:
        req_file = os.path.join(path, "requirements.txt")
        if os.path.exists(req_file):
            print(f"-> {path}/requirements.txt 설치 중...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])

    print("\n" + "="*60)
    print("모든 설치가 완료되었습니다! 이제 run_all.py를 실행할 수 있습니다.")
    print("="*60)

if __name__ == "__main__":
    install_all()