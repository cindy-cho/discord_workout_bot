"""
운동 봇 이벤트 핸들러 모듈 (Workout Bot Events)
------------------------------------------------
- 메시지 이벤트 처리 (첨부파일 감지 및 자동 응답)
- 일일 운동 체크 스케줄러 (매일 22:00 KST)
- 일일 운동 요약 스케줄러 (매일 23:30 KST)
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import pytz
import random
import asyncio

# 설정 import
from workout_bot_config import DISCORD_CHANNEL_ID
from workout_bot_commands import send_alert_to_channel
from workout_bot_messages import encouragement_messages, reminder_messages, encourage_solo_messages

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def setup_events(client, channel_id):
    """이벤트 핸들러들을 설정하는 함수"""
    
    def get_today_thread_name(now=None):
        """오늘 날짜에 해당하는 스레드 이름을 생성합니다"""
        if now is None:
            now = datetime.now(KST)
        date_str = f"{now.month}월 {now.day}일"
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        weekday_name = weekday_names[now.weekday()]
        return f"{date_str} {weekday_name}"
    
    async def get_channel_by_id(channel_id, function_name):
        """채널 ID로 채널을 가져오고 유효성을 검사합니다"""
        channel = client.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            error_msg = f"채널 ID {channel_id}를 찾을 수 없습니다."
            print(f"❌ {error_msg}")
            await send_alert_to_channel(client, error_msg, "Error", f"workout_bot_events.py - {function_name}")
            return None
        return channel
    
    async def find_today_thread(channel, thread_name, function_name):
        """오늘의 스레드를 찾습니다"""
        today_thread = None
        for thread in channel.threads:
            if thread.name == thread_name:
                today_thread = thread
                break
        
        if not today_thread:
            print(f"ℹ️ 오늘의 스레드 '{thread_name}'을 찾을 수 없습니다.")
            return None
            
        print(f"🔍 오늘의 스레드 '{thread_name}'에서 운동 기록을 확인합니다...")
        return today_thread
    
    async def count_workout_records(thread):
        """스레드에서 운동 기록(첨부파일)을 카운팅합니다"""
        workout_count = 0
        workout_users = set()
        
        async for message in thread.history(limit=None):
            # 봇이 아니고 첨부파일이 있는 메시지만 카운트
            if not message.author.bot and message.attachments:
                workout_count += 1
                workout_users.add(message.author.display_name)
        
        print(f"📊 오늘의 운동 기록: {workout_count}개, 참여자: {len(workout_users)}명")
        return workout_count, workout_users
    
    def create_streak_message(user_name, streak_days):
        """연속 운동일수 칭찬 메시지를 생성합니다"""
        if streak_days <= 0:
            return None
        
        # 메시지 import
        from workout_bot_messages import (
            streak_beginner_messages,
            streak_building_messages, 
            streak_established_messages,
            streak_master_messages
        )
        
        # 구간별 메시지 선택
        if streak_days <= 1:
            # 1일: 건조한 메시지
            return f"연속 운동 {streak_days}일째."
        elif 2 <= streak_days <= 4:
            # 2~4일: 시작 단계
            message_template = random.choice(streak_beginner_messages)
            return message_template.format(user=user_name, streak_days=streak_days)
        elif 5 <= streak_days <= 7:
            # 5~7일: 습관 형성 단계
            message_template = random.choice(streak_building_messages)
            return message_template.format(user=user_name, streak_days=streak_days)
        elif 8 <= streak_days <= 12:
            # 8~12일: 확립 단계
            message_template = random.choice(streak_established_messages)
            return message_template.format(user=user_name, streak_days=streak_days)
        else:
            # 13일 이상: 마스터 단계
            message_template = random.choice(streak_master_messages)
            return message_template.format(user=user_name, streak_days=streak_days)
    
    @client.event
    async def on_message(message):
        """
        새로운 메시지가 올 때마다 호출되는 이벤트 핸들러.
        운동 기록(첨부파일)이 업로드되면 자동으로 응답합니다.
        """
        # 봇 자신의 메시지는 무시
        if message.author == client.user:
            return
        
        # 타겟 채널 또는 그 채널의 스레드에서만 처리
        is_target_channel = message.channel.id == channel_id
        is_target_thread = (isinstance(message.channel, discord.Thread) and 
                           message.channel.parent_id == channel_id)
        
        if is_target_channel or is_target_thread:
            # 첨부파일이 있는 메시지 (운동 기록)인 경우
            if message.attachments:
                # 길드 멤버 정보를 통해 실제 이름 가져오기
                try:
                    if isinstance(message.channel, discord.Thread):
                        guild = message.channel.guild
                        member = guild.get_member(message.author.id)
                        user_display_name = member.display_name if member else message.author.display_name
                    else:
                        user_display_name = message.author.display_name
                except Exception as e:
                    print(f"   ⚠️ 멤버 정보 가져오기 실패: {e}")
                    user_display_name = message.author.display_name
                
                channel_name = message.channel.name if isinstance(message.channel, discord.Thread) else "메인 채널"
                print(f"💪 운동 기록 감지! 사용자: {user_display_name}, 채널/스레드: {channel_name}")
                
                # 운동 스레드에서 첨부파일 업로드 시 자동 응답
                if isinstance(message.channel, discord.Thread):
                    # 사용자의 연속 운동일수 조회
                    try:
                        from workout_bot_database import calculate_user_workout_streak
                        from datetime import date, timedelta
                        
                        # 어제 날짜까지의 연속 운동일수를 계산하고 오늘 운동을 더해서 +1
                        yesterday = date.today() - timedelta(days=1)
                        user_streak = calculate_user_workout_streak(client, user_display_name, yesterday) + 1
                        print(f"📈 {user_display_name}님의 연속 운동일수: {user_streak}일")
                    except Exception as streak_error:
                        print(f"❌ 연속 운동일수 조회 중 오류: {streak_error}")
                        user_streak = 0
                    
                    reactions = ["💪", "🔥", "👏", "💯", "🎉"]
                    # 요일별로 다른 리액션 추가
                    now = datetime.now(KST)
                    reaction = reactions[now.weekday() % len(reactions)]
                    try:
                        await message.add_reaction(reaction)
                        # 100% 확률로 응원 메시지 전송
                        # 메시지에서 {user} 플레이스홀더를 실제 사용자명으로 치환
                        formatted_messages = [msg.format(user=user_display_name) for msg in encouragement_messages]
                        encouragement_msg = f"@everyone {random.choice(formatted_messages)}"
                        
                        # 연속 운동일수 칭찬 메시지 추가
                        streak_message = create_streak_message(user_display_name, user_streak)
                        
                        # 두 메시지를 합쳐서 한 번에 전송
                        if streak_message:
                            combined_message = f"{encouragement_msg}. {streak_message}"
                        else:
                            combined_message = encouragement_msg
                        
                        await message.reply(combined_message)
                    except discord.errors.Forbidden:
                        print("리액션 추가 권한이 없습니다.")
                    except Exception as e:
                        print(f"리액션 추가 중 오류: {e}")
                        await send_alert_to_channel(client, f"리액션 추가 중 오류: {e}", "Error", "workout_bot_events.py - on_message")
        
        # 명령어 처리를 위해 필요 (commands.Bot 사용 시)
        await client.process_commands(message)

    @tasks.loop(time=time(hour=1, minute=0))  # UTC 01:00 = KST 10:00
    async def daily_workout_check():
        """
        매일 오전 10시에 실행되는 함수.
        오늘의 운동 스레드를 생성합니다.
        """
        try:
            now = datetime.now(KST)
            print(f"🕙 [{now.strftime('%Y-%m-%d %H:%M')}] 일일 운동 체크를 시작합니다... (10:00 KST)")
            
            # 채널 검증
            channel = await get_channel_by_id(channel_id, "daily_workout_check")
            if not channel:
                return
            
            # 스케줄러에서 스레드 생성 함수 호출
            from workout_bot_schedulers import create_daily_workout_thread
            await create_daily_workout_thread(client, channel_id)
            
        except Exception as e:
            error_msg = f"일일 운동 체크 중 오류 발생: {e}"
            print(f"❌ {error_msg}")
            await send_alert_to_channel(client, e, "Error", "workout_bot_events.py - daily_workout_check")

    @daily_workout_check.before_loop
    async def before_daily_workout_check():
        """일일 운동 체크 시작 전 봇이 준비될 때까지 대기"""
        await client.wait_until_ready()
        now = datetime.now(KST)
        print(f"⏰ 일일 운동 체크 스케줄러가 시작되었습니다. (UTC 01:00 = KST 10:00 실행)")
        print(f"🔍 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    @tasks.loop(time=time(hour=13, minute=0))  # UTC 13:00 = KST 22:00
    async def daily_workout_reminder():
        """
        매일 밤 10시에 실행되는 함수.
        오늘의 운동 스레드에 아무도 운동 기록을 안 올렸는지 확인하고 알림을 보냅니다.
        """
        try:
            now = datetime.now(KST)
            print(f"🕙 [{now.strftime('%Y-%m-%d %H:%M')}] 일일 운동 리마인더를 시작합니다... (22:00 KST)")
            
            # 채널 검증
            channel = await get_channel_by_id(channel_id, "daily_workout_reminder")
            if not channel:
                return
            
            # 오늘 스레드 이름 생성
            today_thread_name = get_today_thread_name(now)
            
            # 오늘의 스레드 찾기
            today_thread = await find_today_thread(channel, today_thread_name, "daily_workout_reminder")
            if not today_thread:
                return
            
            # 운동 기록 카운팅
            workout_count, workout_users = await count_workout_records(today_thread)
            
            # 운동 기록이 없는 경우 스레드 안에 알림 메시지 전송
            if workout_count == 0:
                # 메시지에서 {thread_name} 플레이스홀더를 실제 스레드명으로 치환
                formatted_messages = [msg.format(thread_name=today_thread_name) for msg in reminder_messages]
                reminder_message = random.choice(formatted_messages)
                
                try:
                    # 메인 채널이 아닌 오늘의 운동 스레드에 알림 메시지 전송
                    await today_thread.send(reminder_message)
                    print(f"✅ 운동 없음 알림 메시지 전송 완료 (스레드 '{today_thread_name}'): {reminder_message}")
                except Exception as e:
                    print(f"❌ 알림 메시지 전송 실패: {e}")
                    await send_alert_to_channel(client, f"알림 메시지 전송 실패: {e}", "Error", "workout_bot_events.py - daily_workout_reminder")
        
        except Exception as e:
            error_msg = f"일일 운동 리마인더 중 오류 발생: {e}"
            print(f"❌ {error_msg}")
            await send_alert_to_channel(client, e, "Error", "workout_bot_events.py - daily_workout_reminder")

    @daily_workout_reminder.before_loop
    async def before_daily_workout_reminder():
        """일일 운동 리마인더 시작 전 봇이 준비될 때까지 대기"""
        await client.wait_until_ready()
        now = datetime.now(KST)
        print(f"⏰ 일일 운동 리마인더 스케줄러가 시작되었습니다. (UTC 13:00 = KST 22:00 실행)")
        print(f"🔍 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    @tasks.loop(time=time(hour=14, minute=30))  # UTC 14:30 = KST 23:30
    async def daily_workout_summary():
        """
        매일 밤 11시 30분에 실행되는 함수.
        오늘의 운동 기록이 있는 경우 격려 메시지를 보냅니다.
        """
        try:
            now = datetime.now(KST)
            print(f"🕚 [{now.strftime('%Y-%m-%d %H:%M')}] 일일 운동 요약을 시작합니다... (23:30 KST)")
            
            # 채널 검증
            channel = await get_channel_by_id(channel_id, "daily_workout_summary")
            if not channel:
                return
            
            # 오늘 스레드 이름 생성
            today_thread_name = get_today_thread_name(now)
            
            # 오늘의 스레드 찾기
            today_thread = await find_today_thread(channel, today_thread_name, "daily_workout_summary")
            if not today_thread:
                return
            
            # 운동 기록 카운팅
            workout_count, workout_users = await count_workout_records(today_thread)
            
            # 정확히 1명만 운동 기록을 올린 경우만 격려 메시지 전송
            if len(workout_users) == 1:
                users_list = list(workout_users)[0]  # 1명이므로 첫 번째 사용자만
                
                print(f"✅ 오늘 운동한 사람: {users_list} (총 {workout_count}개 기록)")
                print("💌 1명만 운동했으므로 격려 메시지를 전송합니다.")
                
                # 1명만 운동했을 때 격려 메시지 전송
                # 메시지에서 {user}와 {count} 플레이스홀더를 실제 값으로 치환
                formatted_messages = [
                    f"@everyone {msg.format(user=users_list, count=len(workout_users))}" 
                    for msg in encourage_solo_messages
                ]
                encourage_message = random.choice(formatted_messages)
                
                try:
                    # 메인 채널이 아닌 오늘의 운동 스레드에 격려 메시지 전송
                    await today_thread.send(encourage_message)
                    print(f"✅ 격려 메시지 전송 완료 (스레드 '{today_thread_name}'): {encourage_message}")
                except Exception as e:
                    print(f"❌ 격려 메시지 전송 실패: {e}")
                    await send_alert_to_channel(client, f"격려 메시지 전송 실패: {e}", "Error", "workout_bot_events.py - daily_workout_summary")
            else:
                if len(workout_users) > 1:
                    print(f"ℹ️ 운동 기록이 {len(workout_users)}명이므로 격려 메시지를 보내지 않습니다. (1명일 때만 격려 메시지 전송)")
                else:
                    print(f"ℹ️ 운동 기록이 {len(workout_users)}명이므로 격려 메시지를 보내지 않습니다. (1명일 때만 격려 메시지 전송)")
        
        except Exception as e:
            error_msg = f"일일 운동 요약 중 오류 발생: {e}"
            print(f"❌ {error_msg}")
            await send_alert_to_channel(client, e, "Error", "workout_bot_events.py - daily_workout_summary")

    @daily_workout_summary.before_loop
    async def before_daily_workout_summary():
        """일일 운동 요약 시작 전 봇이 준비될 때까지 대기"""
        await client.wait_until_ready()
        now = datetime.now(KST)
        print("⏰ 일일 운동 요약 스케줄러가 시작되었습니다. (UTC 14:30 = KST 23:30 실행)")
        print(f"🔍 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # 스케줄러들을 시작하는 함수
    def start_event_schedulers():
        """이벤트 관련 스케줄러들을 시작합니다"""
        print("🔄 일일 운동 체크 스케줄러 시작을 시도합니다...")
        if not daily_workout_check.is_running():
            daily_workout_check.start()
            print("✅ 일일 운동 체크 스케줄러가 시작되었습니다.")
        else:
            print("ℹ️ 일일 운동 체크 스케줄러가 이미 실행 중입니다.")
        
        print("🔄 일일 운동 리마인더 스케줄러 시작을 시도합니다...")
        if not daily_workout_reminder.is_running():
            daily_workout_reminder.start()
            print("✅ 일일 운동 리마인더 스케줄러가 시작되었습니다.")
        else:
            print("ℹ️ 일일 운동 리마인더 스케줄러가 이미 실행 중입니다.")
        
        print("🔄 일일 운동 요약 스케줄러 시작을 시도합니다...")
        if not daily_workout_summary.is_running():
            daily_workout_summary.start()
            print("✅ 일일 운동 요약 스케줄러가 시작되었습니다.")
        else:
            print("ℹ️ 일일 운동 요약 스케줄러가 이미 실행 중입니다.")

    return start_event_schedulers
