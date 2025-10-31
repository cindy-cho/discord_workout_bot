import discord
from datetime import datetime, timedelta
import pytz
import random
from collections import Counter

from workout_bot_messages import workout_info_messages

KST = pytz.timezone("Asia/Seoul")

def setup_schedulers(client, channel_id):
    def start_schedulers():
        print("✅ 운동 스케줄러 모듈이 로드되었습니다.")
        print("📋 등록된 스케줄러: 일일 운동 체크, 일일 운동 요약")
    return start_schedulers

async def create_daily_workout_thread(client, channel_id):
    channel = client.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        print(f"❌ 채널 ID {channel_id}에 해당하는 텍스트 채널을 찾을 수 없습니다.")
        return
    
    now = datetime.now(KST)
    date_str = f"{now.month}월 {now.day}일"
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_name = weekday_names[now.weekday()]
    expected_thread_name = f"{date_str} {weekday_name}"
    
    recent_threads = sorted(channel.threads, key=lambda t: t.created_at, reverse=True)[:10]
    if any(t.name == expected_thread_name for t in recent_threads):
        print(f"✅ 오늘의 운동 스레드 '{expected_thread_name}'은(는) 이미 존재합니다.")
        return
    
    weekday_emojis = {0: "💪", 1: "🔥", 2: "💯", 3: "⚡", 4: "🚀", 5: "🌟", 6: "✨"}
    emoji = weekday_emojis[now.weekday()]
    
    try:
        thread_message = "💪 이 스레드에서 오늘의 운동을 기록해보세요!"
        if now.weekday() == 6:
            thread_message += "\n\n한 주 마무리! 다음 주도 화이팅! 🎉"
        
        # 랜덤 운동 정보 메시지 추가
        random_workout_info = random.choice(workout_info_messages)
        thread_message += f"\n\n💡 **오늘의 운동 팁**: {random_workout_info}"
        
        print(f"ℹ️ 오늘의 운동 스레드 '{expected_thread_name}'을(를) 생성합니다.")
        message = await channel.send(f"{date_str} {weekday_name} {emoji}")
        thread = await message.create_thread(name=expected_thread_name, auto_archive_duration=10080)
        await thread.send(thread_message)
        print(f"🧵 스레드가 성공적으로 생성되었습니다: {thread.name}")
    except Exception as e:
        print(f"❌ 스레드 생성에 실패했습니다: {e}")

async def weekly_stats_auto(channel, client, channel_id):
    try:
        now = datetime.now(KST)
        days_to_subtract = now.weekday() + 7
        start_of_prev_week = now - timedelta(days=days_to_subtract)
        start_of_prev_week = start_of_prev_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_prev_week = start_of_prev_week + timedelta(days=6)
        
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        valid_thread_names = set()
        for i in range(7):
            current_day = start_of_prev_week + timedelta(days=i)
            date_str = f"{current_day.month}월 {current_day.day}일"
            weekday_name = weekday_names[current_day.weekday()]
            valid_thread_names.add(f"{date_str} {weekday_name}")

        if not isinstance(channel, discord.TextChannel):
            print(f"❌ 채널 ID {channel_id}를 찾을 수 없습니다.")
            return

        guild = channel.guild
        user_counts = Counter()
        threads_to_check = []
        
        for thread in channel.threads:
            if thread.name in valid_thread_names:
                threads_to_check.append(thread)
        
        try:
            async for thread in channel.archived_threads(limit=50):
                if thread.name in valid_thread_names:
                    threads_to_check.append(thread)
        except discord.errors.Forbidden:
            print("🔐 보관된 스레드를 읽을 권한이 없습니다.")

        for thread in threads_to_check:
            counted_users_in_thread = set()
            async for message in thread.history(limit=None):
                if not message.author.bot and message.attachments and message.author.id not in counted_users_in_thread:
                    try:
                        member = await guild.fetch_member(message.author.id)
                    except discord.NotFound:
                        member = message.author
                    counted_users_in_thread.add(message.author.id)
                    user_counts[member] += 1

        if not user_counts:
            no_stats_message = f"📅 **지난주 운동왕 ({start_of_prev_week.strftime('%m월 %d일')} ~ {end_of_prev_week.strftime('%m월 %d일')})** 🏆\n\n"
            no_stats_message += "😢 아무도 운동을 하지 않았어요... 이번 주에는 더 열심히 해봐요! 💪"
            try:
                await channel.send(no_stats_message)
                print("✅ 운동 기록 없음 메시지가 채널에 전송되었습니다.")
            except Exception as e:
                print(f"❌ 메시지 전송 중 오류 발생: {e}")
            return

        stats_message = f"📅 **지난주 운동왕 ({start_of_prev_week.strftime('%m월 %d일')} ~ {end_of_prev_week.strftime('%m월 %d일')})** 🏆\n\n"
        
        sorted_users = sorted(user_counts.items(), key=lambda item: item[1], reverse=True)
        count_groups = {}
        for user, count in sorted_users:
            if count not in count_groups:
                count_groups[count] = []
            count_groups[count].append(user.display_name)
        
        sorted_counts = sorted(count_groups.keys(), reverse=True)
        current_rank = 0
        for count in sorted_counts:
            users_with_same_count = count_groups[count]
            rank_emoji = {0: "🥇", 1: "🥈", 2: "🥉"}.get(current_rank, "💪")
            users_str = ", ".join(users_with_same_count)
            stats_message += f"{rank_emoji} **{users_str}**: {count}회\n"
            current_rank += 1

        try:
            await channel.send(stats_message)
            print("✅ 전주 통계 메시지가 채널에 전송되었습니다.")
        except Exception as e:
            print(f"❌ 통계 메시지 전송 중 오류 발생: {e}")

    except Exception as e:
        print(f"❌ 주간 통계 집계 중 오류 발생: {e}")
