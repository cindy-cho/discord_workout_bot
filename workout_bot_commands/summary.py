"""
요약 명령어 모듈
==============
!요약 명령어를 정의합니다.
멤버별 운동 요약 정보를 제공합니다.
"""

import discord
from datetime import datetime, timedelta
from workout_bot_database import WorkoutDatabase
from .utils import get_bot_footer, send_error_to_error_channel, KST

def setup_summary_command(client):
    """요약 명령어를 등록하는 함수"""
    
    @client.command(name='요약')
    async def workout_summary_command(ctx):
        """멤버별 운동 요약 정보를 보여주는 명령어"""
        cursor = None
        db = None
        try:
            print(f"📊 {ctx.author.display_name}이(가) !요약 명령어를 실행했습니다.")
            
            # 데이터베이스 연결
            db = WorkoutDatabase()
            if not db.connect():
                await send_error_to_error_channel(
                    client, 
                    "데이터베이스 연결 실패", 
                    "DatabaseConnectionError", 
                    "!요약 명령어",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                return
                
            cursor = db.connection.cursor()
            
            # 모든 운동 멤버 정보 조회
            cursor.execute("SELECT user_name, user_id, total_workout_days, total_days, workout_rate, current_streak, max_streak, last_workout_date FROM workout_members ORDER BY total_workout_days DESC")
            members = cursor.fetchall()
            
            if not members:
                await send_error_to_error_channel(
                    client, 
                    "운동 기록 없음", 
                    "NoDataError", 
                    "!요약 명령어",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                return
            
            # 현재 날짜 및 이번 주 정보 계산
            now = datetime.now(KST)
            today = now.date()
            
            # 이번 주 시작일 (월요일) 계산
            days_since_monday = today.weekday()
            this_week_start = today - timedelta(days=days_since_monday)
            
            # 임베드 메시지 생성
            summary_embed = discord.Embed(
                title="📊 멤버별 운동 요약", 
                description="모든 운동 멤버들의 요약 정보입니다.",
                color=0x00ff80
            )
            
            for idx, member in enumerate(members, 1):
                user_name, user_id, total_workout_days, total_days, workout_rate, current_streak, max_streak, last_workout_date = member
                
                # 이번 주 운동 일수 조회
                this_week_query = """
                SELECT COUNT(*) as workout_count 
                FROM daily_workout_records 
                WHERE user_id = %s AND date >= %s AND date <= %s AND exercised = 'Y'
                """
                cursor.execute(this_week_query, (user_id, this_week_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
                this_week_result = cursor.fetchone()
                this_week_workouts = this_week_result[0] if this_week_result else 0
                
                # 이번 주 진행률 계산 (월~일 7일 기준)
                days_passed_this_week = min(days_since_monday + 1, 7)  # 월요일=1, 화요일=2, ..., 일요일=7
                this_week_rate = (this_week_workouts / days_passed_this_week) * 100 if days_passed_this_week > 0 else 0
                
                # 연속 운동 중인지 확인
                streak_status = "🔥" if current_streak > 0 else "💤"
                
                # 마지막 운동일 표시
                if last_workout_date:
                    if isinstance(last_workout_date, str):
                        last_date = datetime.strptime(last_workout_date, '%Y-%m-%d').date()
                    else:
                        last_date = last_workout_date
                    
                    if last_date == today:
                        last_workout_display = "오늘"
                    elif last_date == today - timedelta(days=1):
                        last_workout_display = "어제"
                    else:
                        days_ago = (today - last_date).days
                        last_workout_display = f"{days_ago}일 전"
                else:
                    last_workout_display = "기록 없음"
                
                summary_embed.add_field(
                    name=f"{idx}. {user_name} {streak_status}",
                    value=f"**총 운동**: {total_workout_days}일/{total_days}일 ({workout_rate:.1f}%)\n"
                          f"**현재 연속**: {current_streak}일 | **최장 연속**: {max_streak}일\n"
                          f"**이번 주**: {this_week_workouts}일/{days_passed_this_week}일 ({this_week_rate:.1f}%)\n"
                          f"**마지막 운동**: {last_workout_display}",
                    inline=False
                )
            
            # 푸터 추가
            summary_embed.set_footer(text=get_bot_footer())
            
            # 메시지 전송
            await ctx.reply(embed=summary_embed)
            print(f"✅ !요약 명령어 실행 완료: {len(members)}명 요약 정보 전송")
            
        except Exception as e:
            print(f"❌ !요약 명령어 실행 중 오류: {e}")
            await send_error_to_error_channel(
                client, 
                f"요약 명령어 실행 중 오류: {str(e)}", 
                type(e).__name__, 
                "!요약 명령어",
                f"{ctx.author.display_name} (ID: {ctx.author.id})"
            )
            await ctx.reply("⏳ 처리 중입니다...")
        finally:
            if cursor:
                cursor.close()
            if db:
                db.disconnect()
    
    print("✅ 요약 명령어 등록 완료")
