"""
추세 명령어 모듈
==============
!추세 명령어를 정의합니다.
운동 추세 분석을 제공합니다.
"""

import discord
from datetime import datetime, timedelta
from workout_bot_database import WorkoutDatabase
from .utils import get_bot_footer, send_error_to_error_channel, KST

def setup_trends_command(client):
    """추세 명령어를 등록하는 함수"""
    
    @client.command(name='추세')
    async def workout_trend_command(ctx):
        """운동 추세 분석을 보여주는 명령어"""
        cursor = None
        db = None
        try:
            print(f"📊 {ctx.author.display_name}이(가) !추세 명령어를 실행했습니다.")
            
            # 데이터베이스 연결
            db = WorkoutDatabase()
            if not db.connect():
                await send_error_to_error_channel(
                    client, 
                    "데이터베이스 연결 실패", 
                    "DatabaseConnectionError", 
                    "!추세 명령어",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                return
            
            cursor = db.connection.cursor()
            now = datetime.now(KST)
            
            # 이번 주 시작일 계산 (월요일)
            today = now.date()
            days_since_monday = today.weekday()
            this_week_start = today - timedelta(days=days_since_monday)
            
            # 5주 전 시작일 계산 (지난주부터 4주를 가져오기 위해)
            five_weeks_ago = this_week_start - timedelta(weeks=5)
            
            # 주간 데이터 조회
            weekly_query = """
            SELECT user_name, year, week_number, week_start_date, week_end_date, workout_days, workout_rate
            FROM weekly_workout_records 
            WHERE week_start_date >= %s
            ORDER BY user_name, year, week_number
            """
            
            cursor.execute(weekly_query, (five_weeks_ago.strftime('%Y-%m-%d'),))
            all_weekly_data = cursor.fetchall()
            
            # 이번 주 데이터 제외하고 정확히 4주만 필터링
            weekly_data = []
            # 4주 전 시작일 계산 (지난주부터 4주)
            four_weeks_ago_start = this_week_start - timedelta(weeks=4)
            
            for row in all_weekly_data:
                user_name, year, week_num, start_date, end_date, workout_days, workout_rate = row
                # start_date가 이번 주 시작일보다 이전이고, 4주 전 시작일 이후인 데이터만 포함
                if isinstance(start_date, str):
                    week_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                else:
                    week_start = start_date
                
                if week_start < this_week_start and week_start >= four_weeks_ago_start:
                    weekly_data.append(row)
            
            print(f"📅 4주간 주간 데이터 {len(weekly_data)}개 조회 완료")
            
            # 사용자별 주간 추세 데이터 구성
            user_weekly_trends = {}
            for row in weekly_data:
                user_name, year, week_num, start_date, end_date, workout_days, workout_rate = row
                
                if user_name not in user_weekly_trends:
                    user_weekly_trends[user_name] = []
                
                user_weekly_trends[user_name].append({
                    'week_start': start_date,
                    'workout_days': workout_days,
                    'workout_rate': workout_rate
                })
            
            # 추세 분석 임베드 생성
            trend_embed = discord.Embed(
                title="📊 운동 추세 분석 (지난주부터 4주)", 
                description="지난주부터 4주간의 운동 데이터를 기반으로 한 추세 분석입니다.",
                color=0x00ff80
            )
            
            if user_weekly_trends:
                for user_name, weekly_data_list in user_weekly_trends.items():
                    # 날짜순 정렬 (오래된 것부터)
                    weekly_data_list.sort(key=lambda x: x['week_start'])
                    
                    if len(weekly_data_list) >= 2:
                        # 추세 분석
                        rates = [data['workout_rate'] for data in weekly_data_list]
                        workout_days_list = [data['workout_days'] for data in weekly_data_list]
                        
                        # 최근 주와 첫 주 비교
                        first_rate = rates[0]
                        last_rate = rates[-1]
                        
                        # 추세 방향 결정
                        rate_diff = last_rate - first_rate
                        
                        if rate_diff > 10:
                            trend_icon = "📈"
                            trend_desc = "상승세"
                        elif rate_diff < -10:
                            trend_icon = "📉"
                            trend_desc = "하락세"
                        else:
                            trend_icon = "➡️"
                            trend_desc = "유지"
                        
                        # 평균 운동 일수 계산
                        avg_workout_days = sum(workout_days_list) / len(workout_days_list)
                        
                        # 주간 데이터 요약
                        weekly_summary = " → ".join([f"{data['workout_days']}일({data['workout_rate']:.0f}%)" for data in weekly_data_list])
                        
                        trend_embed.add_field(
                            name=f"👤 {user_name} {trend_icon} {trend_desc}",
                            value=f"**주간 변화**: {weekly_summary}\n"
                                  f"**운동율 변화**: {first_rate:.0f}% → {last_rate:.0f}% ({rate_diff:+.0f}%p)\n"
                                  f"**평균 운동**: {avg_workout_days:.1f}일/주",
                            inline=False
                        )
                    else:
                        # 데이터가 1주만 있는 경우
                        data = weekly_data_list[0]
                        trend_embed.add_field(
                            name=f"👤 {user_name} ⚠️ 데이터 부족",
                            value=f"**운동 기록**: {data['workout_days']}일 ({data['workout_rate']:.0f}%)\n"
                                  f"**분석**: 1주 데이터만 있어 추세 분석 불가",
                            inline=False
                        )
                
                if len(user_weekly_trends) >= 2:
                    # 전체 평균 추세 계산
                    all_first_rates = []
                    all_last_rates = []
                    
                    for user_name, weekly_data_list in user_weekly_trends.items():
                        if len(weekly_data_list) >= 2:
                            rates = [data['workout_rate'] for data in weekly_data_list]
                            all_first_rates.append(rates[0])
                            all_last_rates.append(rates[-1])
                    
                    if all_first_rates and all_last_rates:
                        avg_first_rate = sum(all_first_rates) / len(all_first_rates)
                        avg_last_rate = sum(all_last_rates) / len(all_last_rates)
                        overall_trend = avg_last_rate - avg_first_rate
                        
                        if overall_trend > 5:
                            overall_icon = "📈"
                            overall_desc = "전체적으로 상승"
                        elif overall_trend < -5:
                            overall_icon = "📉"
                            overall_desc = "전체적으로 하락"
                        else:
                            overall_icon = "➡️"
                            overall_desc = "전체적으로 유지"
                        
                        trend_embed.add_field(
                            name=f"🏆 전체 추세 {overall_icon}",
                            value=f"**{overall_desc}**: {avg_first_rate:.0f}% → {avg_last_rate:.0f}% ({overall_trend:+.0f}%p)",
                            inline=False
                        )
                else:
                    trend_embed.add_field(
                        name="📊 추세 분석 불가",
                        value="충분한 주간 데이터가 없어 추세를 분석할 수 없습니다.",
                        inline=False
                    )
            else:
                trend_embed.add_field(
                    name="📊 데이터 없음",
                    value="지난주부터 4주간 운동 기록이 없어 추세를 분석할 수 없습니다.",
                    inline=False
                )
            
            trend_embed.set_footer(text=get_bot_footer("📅 분석 기준: 지난주부터 4주 데이터 (이번 주 제외)"))
            
            await ctx.reply(embed=trend_embed)
            print(f"✅ !추세 명령어 실행 완료: 추세 분석 전송")
            
        except Exception as e:
            print(f"❌ !추세 명령어 실행 중 오류: {e}")
            await send_error_to_error_channel(
                client, 
                f"추세 명령어 실행 중 오류: {str(e)}", 
                type(e).__name__, 
                "!추세 명령어",
                f"{ctx.author.display_name} (ID: {ctx.author.id})"
            )
            await ctx.reply("⏳ 처리 중입니다...")
        finally:
            if cursor:
                cursor.close()
            if db:
                db.disconnect()
    
    print("✅ 추세 명령어 등록 완료")
