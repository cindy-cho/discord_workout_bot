"""
운동 봇 명령어 패키지
==================
Discord 봇의 명령어들을 정의하는 패키지입니다.

모듈 구조:
- utils.py: 공통 유틸리티 함수들
- summary.py: !요약 명령어
- statistics.py: !통계 명령어  
- trends.py: !추세 명령어
- sync.py: !동기화 명령어
- help.py: /도움 명령어 (slash command)
"""

from .utils import (
    get_bot_footer,
    send_alert_to_channel,
    send_error_to_error_channel
)

from .summary import setup_summary_command
from .statistics import setup_statistics_command
from .trends import setup_trends_command
from .sync import setup_sync_command
from .help import setup_help_command

def setup_commands(client):
    """Discord 봇에 명령어들을 등록하는 함수"""
    print("🔄 운동 봇 명령어 로딩 시작...")
    
    # 각 명령어 모듈 등록
    setup_summary_command(client)
    setup_statistics_command(client)
    setup_trends_command(client)
    setup_sync_command(client)
    setup_help_command(client)
    
    print("✅ 운동 명령어 모듈이 로드되었습니다.")
    print("📋 등록된 명령어: /도움 (slash), !요약, !통계, !추세, !동기화")
    print("🛡️ 명령어 에러 핸들링이 활성화되었습니다.")
