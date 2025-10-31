"""
동기화 명령어 모듈
================
!동기화 명령어를 정의합니다.
운동 스레드 사진 업로드 현황 분석 및 데이터베이스 동기화
"""

import discord
from discord.ext import commands
from datetime import datetime
from workout_bot_config import DISCORD_CHANNEL_ID
from .utils import get_bot_footer, send_error_to_error_channel, KST
from .sync_helpers import (
    WorkoutThreadPhotoCollector,
    update_database_with_workout_data
)

def setup_sync_command(client):
    """동기화 명령어를 등록하는 함수"""
    
    @client.command(name='동기화')
    async def sync_messages_command(ctx, days: int = 7):
        """운동 스레드에서 사용자별 사진 업로드 현황을 분석하는 명령어"""
        try:
            # 🥚 이스터에그: 1995년도 입력시 365일 분석
            easter_egg_mode = False
            if days == 1995:
                days = 365
                easter_egg_mode = True
            
            # 일수 제한 확인 (이스터에그 모드가 아닐 때만)
            if not easter_egg_mode and days > 30:
                await ctx.reply("❌ 최대 30일까지만 분석할 수 있습니다.")
                return
            elif days < 1:
                await ctx.reply("❌ 최소 1일 이상이어야 합니다.")
                return
            
            print(f"🔄 {ctx.author.display_name}이(가) !동기화 {days}일 명령어를 실행했습니다.")
            
            # 초기 응답
            initial_message = await ctx.reply(f"🔍 최근 {days}일간의 운동 스레드에서 사진 업로드 현황을 분석하고 있습니다...")
            
            # 운동 스레드 사진 수집기 생성
            collector = WorkoutThreadPhotoCollector(client)
            
            # 사진 수집 실행 (고정된 채널에서 수집)
            success = await collector.collect_workout_photos(days_back=days)
            
            if success:
                # 수집된 데이터를 데이터베이스에 업데이트
                db_update_success = await update_database_with_workout_data(client, collector)
                
                # 통계 임베드 생성
                stats_embed = discord.Embed(
                    title="📊 운동 스레드 사진 업로드 현황",
                    description=f"최근 {days}일간의 운동 스레드 사진 업로드 분석이 완료되었습니다!",
                    color=0x00ff80,
                    timestamp=datetime.now(KST)
                )
                
                # 수집 채널 정보 가져오기
                collection_channel = client.get_channel(DISCORD_CHANNEL_ID)
                collection_channel_name = collection_channel.name if collection_channel else "알 수 없음"
                
                # 기본 통계
                stats_embed.add_field(
                    name="📈 기본 통계",
                    value=f"""
                    **수집된 스레드 수**: {collector.total_threads_found}개
                    **총 사진 업로드 횟수**: {collector.total_photos_found}회
                    **분석 기간**: 최근 {days}일
                    **수집 채널**: #{collection_channel_name}
                    **데이터베이스 업데이트**: {'✅ 성공' if db_update_success else '❌ 실패'}
                    """.strip(),
                    inline=False
                )
                
                # 사용자별 총 업로드 횟수 계산
                user_totals = {}
                for date_data in collector.workout_data.values():
                    for user_name in date_data:
                        user_totals[user_name] = user_totals.get(user_name, 0) + 1
                
                # 상위 사용자들 표시
                if user_totals:
                    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
                    top_users_text = "\n".join([f"**{user}**: {count}일" for user, count in sorted_users[:10]])
                    
                    stats_embed.add_field(
                        name="🏆 사용자별 업로드 현황 (TOP 10)",
                        value=top_users_text,
                        inline=False
                    )
                
                # 일별 업로드 현황
                daily_summary = []
                for date_key in sorted(collector.workout_data.keys(), reverse=True):
                    date_data = collector.workout_data[date_key]
                    upload_count = len(date_data)
                    
                    if upload_count > 0:
                        daily_summary.append(f"**{date_key}**: {upload_count}명")
                    else:
                        daily_summary.append(f"**{date_key}**: 업로드 없음")
                
                if daily_summary:
                    daily_text = "\n".join(daily_summary[:7])  # 최근 7일만 표시
                    stats_embed.add_field(
                        name="📅 일별 업로드 현황",
                        value=daily_text,
                        inline=True
                    )
                
                stats_embed.set_footer(text=get_bot_footer(f"🔄 사진 업로드 분석 완료"))
                
                # 메시지 수정
                await initial_message.edit(content=None, embed=stats_embed)
                print(f"✅ !동기화 명령어 실행 완료: {collector.total_threads_found}개 스레드, {collector.total_photos_found}회 사진 업로드 분석")
                
            else:
                error_embed = discord.Embed(
                    title="❌ 분석 실패",
                    description="운동 스레드 사진 업로드 분석 중 오류가 발생했습니다.",
                    color=0xff0000,
                    timestamp=datetime.now(KST)
                )
                error_embed.set_footer(text=get_bot_footer("❌ 분석 실패"))
                
                await initial_message.edit(content=None, embed=error_embed)
                print(f"❌ !동기화 명령어 실행 실패")
                
        except Exception as e:
            print(f"❌ !동기화 명령어 실행 중 오류: {e}")
            await send_error_to_error_channel(
                client, 
                f"동기화 명령어 실행 중 오류: {str(e)}", 
                type(e).__name__, 
                "!동기화 명령어",
                f"{ctx.author.display_name} (ID: {ctx.author.id})"
            )
            try:
                await ctx.reply("❌ 분석 중 오류가 발생했습니다. 관리자에게 문의해주세요.")
            except:
                pass  # 이미 응답한 경우 무시

    # 명령어 에러 핸들러 등록
    @client.event
    async def on_command_error(ctx, error):
        """명령어 실행 중 발생하는 오류를 처리하는 이벤트 핸들러"""
        try:
            print(f"🚨 명령어 에러 발생: {type(error).__name__}")
            print(f"   사용자: {ctx.author.display_name} (ID: {ctx.author.id})")
            print(f"   입력 메시지: '{ctx.message.content}'")
            print(f"   채널: #{ctx.channel.name}")
            print(f"   시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
            
            if isinstance(error, commands.CommandNotFound):
                # 존재하지 않는 명령어 처리
                command_name = ctx.message.content.split()[0] if ctx.message.content else "알 수 없음"
                
                print(f"📝 CommandNotFound 처리 시작: {command_name}")
                
                # 에러 메시지 임베드 생성
                error_embed = discord.Embed(
                    title="❌ 명령어를 찾을 수 없습니다",
                    description=f"`{command_name}` 명령어는 존재하지 않습니다.",
                    color=0xff0000
                )
                
                error_embed.add_field(
                    name="🤖 사용 가능한 명령어",
                    value="""
                    • `!요약` - 멤버별 운동 요약 정보
                    • `!통계` - 월별/주간 운동 통계
                    • `!추세` - 운동 추세 분석
                    • `!동기화 [일수]` - 운동 스레드 사진 업로드 현황 분석
                    """.strip(),
                    inline=False
                )
                
                error_embed.add_field(
                    name="💡 도움말",
                    value="자세한 사용법은 `/도움` 명령어를 입력해보세요!",
                    inline=False
                )
                
                error_embed.set_footer(text=get_bot_footer())
                
                print(f"📤 에러 메시지 임베드 생성 완료")
                print(f"   제목: {error_embed.title}")
                print(f"   설명: {error_embed.description}")
                print(f"   필드 수: {len(error_embed.fields)}")
                
                await ctx.reply(embed=error_embed)
                print(f"✅ 답글 형태로 에러 메시지 전송 완료")
                print(f"❌ {ctx.author.display_name}이(가) 존재하지 않는 명령어를 실행했습니다: {command_name}")
                
            elif isinstance(error, commands.MissingRequiredArgument):
                # 필수 인자가 누락된 경우
                print(f"📝 MissingRequiredArgument 처리 시작")
                print(f"   누락된 매개변수: {error.param}")
                
                await send_error_to_error_channel(
                    client, 
                    f"필수 인자 누락: {error.param}", 
                    "MissingRequiredArgument", 
                    "명령어 실행",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                
            elif isinstance(error, commands.BadArgument):
                # 잘못된 인자 타입인 경우
                await send_error_to_error_channel(
                    client, 
                    f"잘못된 인자: {str(error)}", 
                    "BadArgument", 
                    "명령어 실행",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                
            elif isinstance(error, commands.CommandOnCooldown):
                # 명령어 쿨다운 중인 경우
                await send_error_to_error_channel(
                    client, 
                    f"명령어 쿨다운: {error.retry_after:.1f}초 남음", 
                    "CommandOnCooldown", 
                    "명령어 실행",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                
            else:
                # 기타 예상치 못한 오류
                print(f"📝 예상치 못한 오류 처리 시작: {type(error).__name__}")
                print(f"   오류 내용: {str(error)}")
                
                await send_error_to_error_channel(
                    client, 
                    f"예상치 못한 명령어 오류: {str(error)}", 
                    type(error).__name__, 
                    "명령어 실행",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
                await ctx.reply("⏳ 처리 중입니다...")
                
        except Exception as e:
            # 에러 핸들러 자체에서 오류가 발생한 경우
            print(f"🚨 에러 핸들러 자체에서 오류 발생!")
            print(f"   오류 타입: {type(e).__name__}")
            print(f"   오류 내용: {str(e)}")
            print(f"   원본 에러: {type(error).__name__}: {str(error)}")
            print(f"❌ 에러 핸들러에서 오류 발생: {e}")
            
            # 에러 핸들러 자체의 오류를 에러 채널에 보고
            try:
                await send_error_to_error_channel(
                    client, 
                    f"에러 핸들러 자체에서 오류 발생: {str(e)}, 원본 에러: {type(error).__name__}: {str(error)}", 
                    "ErrorHandlerFailure", 
                    "on_command_error",
                    f"{ctx.author.display_name} (ID: {ctx.author.id})"
                )
            except Exception as error_channel_error:
                print(f"🚨 에러 채널 보고도 실패: {error_channel_error}")
            
            try:
                await ctx.reply("❌ 시스템 오류가 발생했습니다. 관리자에게 문의해주세요.")
                print(f"✅ 긴급 오류 메시지 전송 완료")
            except Exception as send_error:
                print(f"🚨 긴급 메시지 전송도 실패: {send_error}")
                pass  # 메시지 전송조차 실패하는 경우 무시
    
    print("✅ 동기화 명령어 등록 완료")
