import subprocess
import sys
import time
import os

def run_all():
    processes = []
    
    # 각 에이전트별 실행 정보 (포트: mental=8000, diet=8001, exercise=8002, orchestrator=9000)
    tasks = [
        {"name": "Mental Agent",   "cmd": [sys.executable, "main.py"], "cwd": "mental_journal_agent"},
        {"name": "Diet Agent",     "cmd": [sys.executable, "main.py"], "cwd": "diet_agent"},
        {"name": "Exercise Agent", "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8002", "--host", "0.0.0.0"], "cwd": "exercise_agent"},
        {"name": "Orchestrator",   "cmd": [sys.executable, "main.py"], "cwd": "orchestrator"},
    ]

    print("="*60)
    print("CareSync 통합 헬스케어 시스템을 시작합니다...")
    print("="*60)
    
    try:
        for task in tasks:
            # 절대 경로 계산
            cwd_path = os.path.join(os.getcwd(), task['cwd'])
            print(f"[{task['name']}] 서버 기동 중... (경로: {task['cwd']})")
            
            # 프로세스 실행
            p = subprocess.Popen(task['cmd'], cwd=cwd_path)
            processes.append(p)
            
            # Mental Agent는 KoNLPy(Java) 초기화 시간이 필요하므로 더 오래 대기
            wait_time = 5 if task['name'] == "Mental Agent" else 2
            time.sleep(wait_time)
        
        print("\n" + "="*60)
        print("모든 서비스가 성공적으로 시작되었습니다!")
        print("  - [8000] 멘탈 저널링 에이전트")
        print("  - [8001] 식단 최적화 에이전트")
        print("  - [8002] 운동 최적화 에이전트")
        print("  - [9000] 통합 오케스트레이터 (메인 UI)")
        print("="*60)
        print("접속 주소: http://localhost:9000")
        print("종료하려면 이 창에서 Ctrl+C를 누르세요.\n")
        
        # 프로세스 유지
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n서비스를 종료하는 중입니다...")
        for p in processes:
            p.terminate()
        print("모든 서버가 안전하게 종료되었습니다.")

if __name__ == "__main__":
    run_all()