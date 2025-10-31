"""
운동 봇 공통 유틸리티 함수들
========================
모든 명령어에서 공통으로 사용하는 함수들을 정의합니다.
"""

import discord
from datetime import datetime
import pytz
import logging
from workout_bot_config import BOT_VERSION, DISCORD_ALERT_CHANNEL_ID

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 로깅 설정
logger = logging.getLogger(__name__)

def get_bot_footer(additional_info=None):
    """봇의 공통 footer 텍스트를 생성하는 함수"""
    now = datetime.now(KST)
    base_footer = f"🦕 근육몬 봇 v{BOT_VERSION} | 제작: 공룡 운동 동호회 | 소스코드보기: https://github.com/cindy-cho/discord_workout_bot"
    
    if additional_info:
        return f"{additional_info} | {base_footer} | 조회 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return f"{base_footer} | 조회 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}"

async def send_alert_to_channel(client, message, alert_type="Info", location="Unknown", user_info=None):
    """알림 채널에 메시지를 전송하는 함수 (에러, 정보, 알림 등)"""
    try:
        alert_channel_id = DISCORD_ALERT_CHANNEL_ID
        if not alert_channel_id:
            print("❌ DISCORD_ALERT_CHANNEL_ID가 설정되지 않았습니다.")
            return
            
        channel = client.get_channel(alert_channel_id)
        if not channel:
            print(f"❌ 알림 채널을 찾을 수 없습니다: {alert_channel_id}")
            return
            
        # 알림 타입에 따른 색상 설정
        color_map = {
            "Error": 0xff0000,      # 빨강
            "Warning": 0xffa500,    # 주황
            "Info": 0x00ff80,       # 초록
            "Success": 0x00ff00,    # 밝은 초록
        }
        color = color_map.get(alert_type, 0x808080)  # 기본 회색
        
        alert_embed = discord.Embed(
            title=f"🤖 {alert_type}",
            description=f"**위치**: {location}\n**메시지**: {message}",
            color=color,
            timestamp=datetime.now(KST)
        )
        
        if user_info:
            alert_embed.add_field(name="👤 사용자", value=user_info, inline=True)
            
        alert_embed.add_field(name="🕐 발생 시간", value=datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        alert_embed.set_footer(text=get_bot_footer())
        
        await channel.send(embed=alert_embed)
        print(f"✅ 알림 메시지를 알림 채널에 전송했습니다: {message}")
        
    except Exception as e:
        print(f"❌ 알림 채널 전송 실패: {e}")

# 기존 함수명과의 호환성을 위한 별칭
async def send_error_to_error_channel(client, error_message, error_type="CommandError", location="Unknown", user_info=None):
    """에러 채널에 에러 메시지를 전송하는 함수 (send_alert_to_channel의 별칭)"""
    await send_alert_to_channel(client, error_message, f"Error - {error_type}", location, user_info)
