"""
운동 스레드 관리 봇 메인 (Workout Thread Bot Main)
------------------------------------------------
- 매일 자동으로 운동 스레드를 생성합니다.
- 주간 통계를 집계하여 사용자별 운동 기록을 보여줍니다.
- Discord 명령어를 통해 운동 요약 및 통계를 조회할 수 있습니다.
- !요약: 멤버별 운동 요약 표시
- !통계: 최근 3개월 월별, 최근 4주 주간 통계 표시
- !추세: 운동 추세 분석 표시
"""

import discord
from discord.ext import commands
from datetime import datetime
import pytz

# 모듈 import
from workout_bot_commands import setup_commands, send_alert_to_channel
from workout_bot_schedulers import setup_schedulers, create_daily_workout_thread, weekly_stats_auto
from workout_bot_events import setup_events
from workout_bot_config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, DISCORD_ALERT_CHANNEL_ID, BOT_VERSION

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용을 읽기 위해 필요
intents.members = True  # 멤버 정보 접근을 위해 필요
client = commands.Bot(command_prefix='!', intents=intents)

token = DISCORD_BOT_TOKEN
channel_id = DISCORD_CHANNEL_ID

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

async def send_error_to_channel(error_message, error_type="Exception", location="Unknown"):
    """에러 발생 시 지정된 채널에 에러 메시지를 전송하는 함수"""
    try:
        await send_alert_to_channel(client, str(error_message), f"Error - {error_type}", location)
        print(f"✅ 에러 메시지가 알림 채널에 전송되었습니다.")
    except Exception as send_error:
        print(f"❌ 에러 메시지 전송 실패: {send_error}")

async def send_bot_startup_notification():
    """봇 시작 알림을 지정된 채널에 전송"""
    try:
        startup_message = f"🚀 근육몬 봇이 성공적으로 시작되었습니다!\n\n" \
                         f"📅 **시작 시간**: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}\n" \
                         f"🤖 **봇 버전**: v{BOT_VERSION}\n" \
                         f"📋 **사용 가능한 명령어**: /도움, !요약, !통계, !추세, !동기화\n" \
                         f"⚙️ **자동화 기능**: 일일 운동 체크, 주간 통계 집계\n" \
                         f"🛡️ **모니터링**: 에러 핸들링 및 알림 시스템 활성화"
        
        await send_alert_to_channel(
            client, 
            startup_message, 
            "Success", 
            "workout_bot_main.py - send_bot_startup_notification"
        )
        print("✅ 봇 시작 알림을 알림 채널에 전송했습니다.")
    except Exception as e:
        print(f"❌ 봇 시작 알림 전송 실패: {e}")

async def sync_slash_commands():
    """Slash commands 동기화"""
    try:
        synced = await client.tree.sync()
        print(f"🔄 Slash commands 동기화 완료: {len(synced)}개 명령어")
    except Exception as e:
        error_msg = f"Slash commands 동기화 실패: {e}"
        print(f"❌ {error_msg}")
        await send_error_to_channel(e, "SlashCommandSyncError", "workout_bot_main.py - sync_slash_commands")

async def start_bot_schedulers():
    """스케줄러 등록 및 시작"""
    try:
        # 기본 스케줄러 설정 및 시작
        start_schedulers = setup_schedulers(client, channel_id)
        start_schedulers()
        
        # 이벤트 관련 스케줄러 설정 및 시작
        start_event_schedulers = setup_events(client, channel_id)
        start_event_schedulers()
        
    except Exception as e:
        error_msg = f"스케줄러 시작 실패: {e}"
        print(f"❌ {error_msg}")
        await send_error_to_channel(e, "SchedulerStartError", "workout_bot_main.py - start_bot_schedulers")

async def handle_monday_tasks():
    """월요일에 실행되는 작업들 (전주 통계 집계 및 스레드 생성)"""
    print("📆 오늘은 월요일입니다.")
    
    try:
        # 운동 스레드 생성 가능성 확인 (중복 스레드가 없는지)
        channel = client.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            error_msg = f"채널 ID {channel_id}에 해당하는 텍스트 채널을 찾을 수 없습니다."
            print(f"❌ {error_msg}")
            await send_error_to_channel(error_msg, "ChannelNotFoundError", "workout_bot_main.py - handle_monday_tasks")
            return
    except Exception as e:
        error_msg = f"채널 확인 중 오류 발생: {e}"
        print(f"❌ {error_msg}")
        await send_error_to_channel(e, "ChannelCheckError", "workout_bot_main.py - handle_monday_tasks")
        return
        
    # 오늘 날짜로 생성될 스레드 이름 정의
    now = datetime.now(KST)
    date_str = f"{now.month}월 {now.day}일"
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_name = weekday_names[now.weekday()]
    expected_thread_name = f"{date_str} {weekday_name}"

    # 활성 스레드 중 최근 10개만 확인하여 중복 여부 확인
    recent_threads = sorted(channel.threads, key=lambda t: t.created_at, reverse=True)[:10]
    thread_exists = any(t.name == expected_thread_name for t in recent_threads)
    
    if not thread_exists:
        # 스레드가 없는 경우에만 전주 통계를 보여주고 새 스레드 생성
        try:
            print("📊 전주 주간 통계를 집계합니다...")
            # 채널 객체를 weekly_stats_auto에 전달하여 통계 메시지를 채널에 직접 전송
            await weekly_stats_auto(channel, client, channel_id)
            # 통계 메시지 전송 후에 오늘의 운동 스레드 생성
            await create_daily_workout_thread(client, channel_id)
            print("✅ 전주 통계 집계 및 스레드 생성 작업 완료. 봇은 계속 실행됩니다.")
        except Exception as e:
            error_msg = f"주간 통계 집계 및 스레드 생성 실패: {e}"
            print(f"❌ {error_msg}")
            await send_error_to_channel(e, "WeeklyStatsAndThreadError", "workout_bot_main.py - handle_monday_tasks")
    else:
        # 이미 오늘의 스레드가 존재함
        print(f"✅ 오늘의 운동 스레드 '{expected_thread_name}'은(는) 이미 존재합니다.")
        print("ℹ️ 오늘의 스레드가 이미 존재하므로 전주 통계는 집계하지 않습니다.")

async def handle_non_monday_tasks():
    """월요일이 아닌 날에 실행되는 작업들 (운동 스레드만 생성)"""
    now = datetime.now(KST)
    try:
        await create_daily_workout_thread(client, channel_id)
        print(f"✅ 스레드 생성 완료. 오늘은 {['월', '화', '수', '목', '금', '토', '일'][now.weekday()]}요일이므로 주간 통계는 집계하지 않습니다.")
    except Exception as e:
        error_msg = f"일일 스레드 생성 실패: {e}"
        print(f"❌ {error_msg}")
        await send_error_to_channel(e, "DailyThreadError", "workout_bot_main.py - handle_non_monday_tasks")

@client.event
async def on_ready():
    """
    봇이 로그인하고 준비되면 자동으로 실행되는 이벤트 핸들러.
    월요일에는 전주 통계를 보여주고 오늘의 운동 스레드를 생성합니다.
    다른 요일에는 운동 스레드만 생성합니다.
    """
    print(f"💪 {client.user}(으)로 로그인되었습니다.")
    
    # 봇 시작 알림 전송
    await send_bot_startup_notification()
    
    # 명령어 등록
    setup_commands(client)
    
    # Slash commands 동기화
    await sync_slash_commands()
    
    # 스케줄러 등록 및 시작
    await start_bot_schedulers()
    
    # 현재 요일에 따른 작업 분기
    now = datetime.now(KST)
    if now.weekday() == 0:  # 0=월요일
        await handle_monday_tasks()
    else:
        await handle_non_monday_tasks()

# 봇 실행
if __name__ == "__main__":
    try:
        print("🚀 운동 스레드 관리 봇 메인을 시작합니다...")
        print("📋 사용 가능한 명령어:")
        print("  /도움 - 명령어 가이드 및 사용법 표시 (개인용)")
        print("  !요약 - 멤버별 운동 요약 표시")
        print("  !통계 - 최근 3개월 월별, 지난주부터 4주 주간 통계 표시")
        print("  !추세 - 운동 추세 분석 표시")
        print("  !동기화 [일수] - 운동 스레드 사진 업로드 현황 분석 (기본: 7일, 최대: 30일)")
        client.run(token)
    except Exception as e:
        print(f"❌ 봇 실행 중 오류 발생: {e}")
        # 봇이 실행되지 않은 상태에서는 Discord API 사용 불가하므로 콘솔 로그만 출력
        print(f"⚠️ 봇 토큰 또는 네트워크 연결을 확인해주세요.")
        print(f"📧 알림 채널 ID: {DISCORD_ALERT_CHANNEL_ID}")
