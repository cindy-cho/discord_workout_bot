"""
도움말 명령어 모듈
================
/도움 슬래시 명령어를 정의합니다.
"""

import discord
from datetime import datetime
from .utils import get_bot_footer, send_error_to_error_channel, KST

def setup_help_command(client):
    """도움말 슬래시 명령어를 등록하는 함수"""
    
    @client.tree.command(name="도움", description="근육몬 봇의 사용법을 알려드립니다")
    async def help_slash_command(interaction: discord.Interaction):
        """도움말을 보여주는 슬래시 명령어 (ephemeral)"""
        try:
            # 즉시 defer하여 응답 시간 확보
            await interaction.response.defer(ephemeral=True)
            
            print(f"💡 {interaction.user.display_name}이(가) /도움 슬래시 명령어를 실행했습니다.")
            
            # 현재 시간 계산
            now = datetime.now(KST)
            
            # 도움말 임베드 생성
            help_embed = discord.Embed(
                title="🦕 근육몬 봇 사용법",
                description="운동 기록 관리를 도와주는 Discord 봇입니다!",
                color=0x00ff80,
                timestamp=now
            )
            
            # 기본 명령어 추가
            help_embed.add_field(
                name="📝 기본 명령어",
                value="""
                `!요약` - 멤버별 운동 요약 정보
                `!통계` - 월별/주간 운동 통계 
                `!추세` - 운동 추세 분석
                `!동기화 [일수]` - 운동 스레드 사진 업로드 현황 분석 (기본: 7일, 최대: 30일)
                `/도움` - 이 도움말 (슬래시 명령어)
                """.strip(),
                inline=False
            )
            
            # 요약 명령어 상세 설명
            help_embed.add_field(
                name="📊 !요약",
                value="""
                **기능**: 멤버별 운동 요약 정보
                **사용법**: `!요약`
                **제공 정보**:
                • 누적 운동 일수 및 운동율
                • 현재 연속 운동 기록
                • 최장 연속 운동 기록
                • 이번 주 운동 진행률
                """.strip(),
                inline=False
            )
            
            # 통계 명령어 상세 설명
            help_embed.add_field(
                name="📈 !통계",
                value="""
                **기능**: 월별/주간 운동 통계
                **사용법**: `!통계`
                **제공 정보**:
                • 월별 통계 (최근 3개월)
                • 주간 통계 (지난주부터 4주)
                • 평균 운동일 및 운동율
                """.strip(),
                inline=False
            )
            
            # 추세 명령어 상세 설명
            help_embed.add_field(
                name="📊 !추세",
                value="""
                **기능**: 운동 추세 분석
                **사용법**: `!추세`
                **제공 정보**:
                • 지난주부터 4주간 추세 분석
                • 개인별 운동율 변화 추세
                • 전체 그룹 평균 추세
                """.strip(),
                inline=False
            )
            
            # 동기화 명령어 상세 설명
            help_embed.add_field(
                name="🔄 !동기화",
                value="""
                **기능**: 운동 스레드 사진 업로드 현황 분석
                **사용법**: `!동기화` 또는 `!동기화 [일수]`
                **제공 정보**:
                • 일별 운동 스레드에서 사용자별 사진 업로드 현황 (기본: 7일, 최대: 30일)
                • 사용자별 총 업로드 일수 랭킹
                • 일별 업로드 참여자 수 현황
                """.strip(),
                inline=False
            )
            
            # 자동화 기능 설명
            help_embed.add_field(
                name="🤖 자동화 기능",
                value="""
                **일간 운동 집계**: 매일 23:50 자동 실행
                **주간 통계 집계**: 매주 월요일 09:00 자동 실행
                **지속적인 모니터링**: 24시간 운동 데이터 추적
                """.strip(),
                inline=False
            )
            
            # 기능 안내
            help_embed.add_field(
                name="✨ 주요 특징",
                value="""
                • **실시간 운동 추적**: 매일 자동으로 운동 데이터 수집
                • **상세한 통계**: 개인별/그룹별 다양한 통계 제공
                • **추세 분석**: 운동 패턴 변화 분석
                • **사용자 친화적**: 직관적인 명령어와 시각적 표현
                예시: `!요약`, `!통계`, `!추세`, `/도움`
                """.strip(),
                inline=False
            )
            
            # 푸터 설정
            help_embed.set_footer(text=get_bot_footer())
            
            # ephemeral로 응답 (본인만 볼 수 있음)
            await interaction.followup.send(embed=help_embed, ephemeral=True)
            print(f"✅ /도움 슬래시 명령어 실행 완료: ephemeral 도움말 전송")
            
        except Exception as e:
            print(f"❌ /도움 슬래시 명령어 실행 중 오류: {e}")
            await send_error_to_error_channel(
                client, 
                f"도움말 슬래시 명령어 실행 중 오류: {str(e)}", 
                type(e).__name__, 
                "/도움 슬래시 명령어",
                f"{interaction.user.display_name} (ID: {interaction.user.id})"
            )
            
            try:
                # 오류 발생 시 간단한 메시지만 전송
                if not interaction.response.is_done():
                    await interaction.response.send_message("⏳ 처리 중입니다...", ephemeral=True)
                else:
                    await interaction.followup.send("⏳ 처리 중입니다...", ephemeral=True)
            except Exception as followup_error:
                print(f"❌ /도움 에러 응답 전송 실패: {followup_error}")
    
    print("✅ 도움말 명령어 등록 완료")
