"""
통계 명령어 모듈
==============
!통계 명령어를 정의합니다.
월별/주간 운동 통계를 제공합니다.
"""

import discord
from datetime import datetime, timedelta
from workout_bot_database import WorkoutDatabase
from .utils import get_bot_footer, send_error_to_error_channel, KST

def setup_statistics_command(client):
    """통계 명령어를 등록하는 함수"""
    
    @client.command(name='통계')
    async def workout_stats_command(ctx):
        """최근 3개월 월별, 최근 4주 주간 통계를 보여주는 명령어"""
        cursor = None
        db = None
        try:
            print(f"📈 {ctx.author.display_name}이(가) !통계 명령어를 실행했습니다.")
            
            # 데이터베이스 연결
            db = WorkoutDatabase()
            if not db.connect():
                await send_error_to_error_channel(
                    client, 
                    "데이터베이스 연결 실패", 
                    "DatabaseConnectionError", 
                    "!통계 명령어",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                return
            
            cursor = db.connection.cursor()
            
            # 현재 날짜 기준 계산
            now = datetime.now(KST)
            
            # === 월별 통계 (최근 3개월) ===
            # 정확히 3개월: 현재 월, 이전 월, 2개월 전
            current_year = now.year
            current_month = now.month
            
            # 3개월치 년월 리스트 생성
            months_to_query = []
            for i in range(3):
                target_month = current_month - i
                target_year = current_year
                
                if target_month <= 0:
                    target_month += 12
                    target_year -= 1
                
                months_to_query.append((target_year, target_month))
            
            print(f"📅 월별 통계 대상 기간: {months_to_query}")
            
            # 모든 workout_members를 기준으로 월별 통계 조회
            monthly_data = []
            for year, month in months_to_query:
                monthly_query = """
                SELECT wm.user_name, %s as year, %s as month,
                       COALESCE(COUNT(dwr.workout_date), 0) as workout_days,
                       COALESCE(COUNT(DISTINCT dwr.workout_date), 0) as unique_workout_days,
                       CASE 
                           WHEN DAY(LAST_DAY(STR_TO_DATE(CONCAT(%s, '-', %s, '-01'), '%%Y-%%m-%%d'))) > 0 
                           THEN ROUND((COALESCE(COUNT(DISTINCT dwr.workout_date), 0) / DAY(LAST_DAY(STR_TO_DATE(CONCAT(%s, '-', %s, '-01'), '%%Y-%%m-%%d')))) * 100, 1)
                           ELSE 0
                       END as workout_rate
                FROM workout_members wm
                LEFT JOIN daily_workout_records dwr ON wm.user_id = dwr.user_id 
                    AND YEAR(dwr.workout_date) = %s 
                    AND MONTH(dwr.workout_date) = %s
                    AND dwr.workout_completed = 1
                GROUP BY wm.user_name
                ORDER BY workout_days DESC
                """
                
                cursor.execute(monthly_query, (year, month, year, month, year, month, year, month))
                month_results = cursor.fetchall()
                
                for row in month_results:
                    monthly_data.append(row)
            
            # === 주간 통계 (최근 4주) ===
            # 모든 workout_members를 기준으로 주간 통계 조회
            today = now.date()
            days_since_monday = today.weekday()
            this_week_start = today - timedelta(days=days_since_monday)
            
            # 지난주부터 4주 전까지 (이번 주 제외)
            four_weeks_ago_start = this_week_start - timedelta(weeks=4)
            last_week_end = this_week_start - timedelta(days=1)
            
            weekly_query = """
            SELECT wm.user_name, wwr.year, wwr.week_number, wwr.week_start_date, wwr.week_end_date, 
                   COALESCE(wwr.workout_days, 0) as workout_days, 
                   COALESCE(wwr.workout_rate, 0) as workout_rate
            FROM workout_members wm
            LEFT JOIN weekly_workout_records wwr ON wm.user_id = wwr.user_id 
                AND wwr.week_start_date >= %s 
                AND wwr.week_end_date <= %s
            ORDER BY wm.user_name, wwr.year, wwr.week_number
            """
            
            cursor.execute(weekly_query, (four_weeks_ago_start.strftime('%Y-%m-%d'), last_week_end.strftime('%Y-%m-%d')))
            weekly_data = cursor.fetchall()
            
            print(f"📅 주간 통계 기간: {four_weeks_ago_start} ~ {last_week_end}")
            print(f"📅 월별 통계 데이터: {len(monthly_data)}개, 주간 통계 데이터: {len(weekly_data)}개")
            
            # === 월별 통계 메시지 생성 ===
            monthly_embed = discord.Embed(
                title="📊 월별 운동 통계 (최근 3개월)", 
                description="최근 3개월간의 월별 운동 통계입니다.",
                color=0x00ff80
            )
            
            if monthly_data:
                # 월별로 그룹화
                monthly_grouped = {}
                for row in monthly_data:
                    user_name, year, month, workout_days, unique_workout_days, workout_rate = row
                    month_key = f"{year}-{month:02d}"
                    
                    if month_key not in monthly_grouped:
                        monthly_grouped[month_key] = []
                    monthly_grouped[month_key].append((user_name, workout_days, workout_rate))
                
                # 월별로 정렬 (최신 월부터)
                for month_key in sorted(monthly_grouped.keys(), reverse=True):
                    year, month = month_key.split('-')
                    month_name = f"{year}년 {int(month)}월"
                    
                    user_stats = monthly_grouped[month_key]
                    user_stats.sort(key=lambda x: x[1], reverse=True)  # 운동일수 기준 정렬
                    
                    if any(stat[1] > 0 for stat in user_stats):  # 운동 기록이 있는 월만 표시
                        stats_text = "\n".join([f"**{name}**: {days}일 ({rate:.1f}%)" for name, days, rate in user_stats if days > 0])
                        if not stats_text:
                            stats_text = "운동 기록이 없습니다."
                        
                        monthly_embed.add_field(
                            name=f"📅 {month_name}",
                            value=stats_text,
                            inline=False
                        )
                
                if not monthly_embed.fields:
                    monthly_embed.add_field(
                        name="📅 통계 없음",
                        value="최근 3개월간 운동 기록이 없습니다.",
                        inline=False
                    )
            
            # === 주간 통계 메시지 생성 ===
            weekly_embed = discord.Embed(
                title="📊 주간 운동 통계 (지난주부터 4주)", 
                description="지난주부터 4주간의 주간 운동 통계입니다.",
                color=0x0080ff
            )
            
            if weekly_data:
                # 주차별로 그룹화
                weekly_grouped = {}
                for row in weekly_data:
                    user_name, year, week_number, week_start_date, week_end_date, workout_days, workout_rate = row
                    
                    if year and week_number:  # NULL이 아닌 경우만
                        week_key = f"{year}-W{week_number:02d}"
                        
                        if week_key not in weekly_grouped:
                            weekly_grouped[week_key] = {
                                'start_date': week_start_date,
                                'end_date': week_end_date,
                                'users': []
                            }
                        weekly_grouped[week_key]['users'].append((user_name, workout_days, workout_rate))
                
                # 주차별로 정렬 (최신 주부터)
                for week_key in sorted(weekly_grouped.keys(), reverse=True):
                    week_info = weekly_grouped[week_key]
                    year, week = week_key.split('-W')
                    
                    # 주차 기간 표시
                    start_date = week_info['start_date']
                    end_date = week_info['end_date']
                    
                    if start_date and end_date:
                        if isinstance(start_date, str):
                            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                        
                        week_name = f"{year}년 {int(week)}주차 ({start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')})"
                    else:
                        week_name = f"{year}년 {int(week)}주차"
                    
                    user_stats = week_info['users']
                    user_stats.sort(key=lambda x: x[1], reverse=True)  # 운동일수 기준 정렬
                    
                    if any(stat[1] > 0 for stat in user_stats):  # 운동 기록이 있는 주만 표시
                        stats_text = "\n".join([f"**{name}**: {days}일 ({rate:.1f}%)" for name, days, rate in user_stats if days > 0])
                        if not stats_text:
                            stats_text = "운동 기록이 없습니다."
                        
                        weekly_embed.add_field(
                            name=f"📅 {week_name}",
                            value=stats_text,
                            inline=False
                        )
                
                if not weekly_embed.fields:
                    weekly_embed.add_field(
                        name="📅 통계 없음",
                        value="지난주부터 4주간 운동 기록이 없습니다.",
                        inline=False
                    )
            else:
                weekly_embed.add_field(
                    name="📅 통계 없음",
                    value="지난주부터 4주간 운동 기록이 없습니다.",
                    inline=False
                )
            
            # 푸터 추가
            monthly_embed.set_footer(text=get_bot_footer())
            weekly_embed.set_footer(text=get_bot_footer())
            
            # 메시지 전송
            await ctx.reply(embed=monthly_embed)
            await ctx.send(embed=weekly_embed)
            
            print(f"✅ !통계 명령어 실행 완료: 월별 {len(set(row[1:3] for row in monthly_data))}개월, 주간 {len(set(row[1:3] for row in weekly_data))}주 통계 전송")
            
        except Exception as e:
            print(f"❌ !통계 명령어 실행 중 오류: {e}")
            await send_error_to_error_channel(
                client, 
                f"통계 명령어 실행 중 오류: {str(e)}", 
                type(e).__name__, 
                "!통계 명령어",
                f"{ctx.author.display_name} (ID: {ctx.author.id})"
            )
            await ctx.reply("⏳ 처리 중입니다...")
        finally:
            if cursor:
                cursor.close()
            if db:
                db.disconnect()
    
    print("✅ 통계 명령어 등록 완료")
