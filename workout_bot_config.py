"""
운동 봇 설정 파일
---------------
Discord 봇의 토큰과 기본 설정값들을 관리합니다.
"""

# 봇 버전 정보
BOT_VERSION = "1.1.0"

# Discord Bot 설정
DISCORD_BOT_TOKEN = {사용자 디스코드 봇 토큰}
DISCORD_CHANNEL_ID = {운동 스레드를 등록할 채널 ID}
DISCORD_ALERT_CHANNEL_ID = {에러 및 알람 받을 채널 ID}

# 데이터베이스 설정 (workout_bot_database.py에서 사용)
DATABASE_CONFIG = {
    "host": {host},
    "port": {port},
    "user": {user},
    "password": {password},
    "database": {database}
}
