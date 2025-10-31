"""
동기화 명령어 관련 헬퍼 함수들
=============================
운동 스레드 사진 수집 및 데이터베이스 업데이트 기능
"""

import discord
import asyncio
from datetime import datetime, timedelta
from workout_bot_database import (
    upsert_daily_workout_record, 
    upsert_weekly_workout_records, 
    upsert_monthly_workout_records,
    update_member_statistics
)
from workout_bot_config import DISCORD_CHANNEL_ID
from .utils import send_alert_to_channel, send_error_to_error_channel, KST

async def update_database_with_workout_data(client, workout_data):
    """
    수집된 운동 스레드 데이터를 데이터베이스에 업데이트하는 함수
    
    Args:
        client: Discord 클라이언트
        workout_data: 수집기 객체 (workout_data 속성과 user_id_mapping 속성 포함)
    
    Returns:
        bool: 성공 여부
    """
    try:
        print("🔄 데이터베이스 업데이트 시작...")
        
        # 수집기 객체에서 데이터 추출
        if hasattr(workout_data, 'workout_data'):
            # WorkoutThreadPhotoCollector 객체인 경우
            data = workout_data.workout_data
            user_id_mapping = getattr(workout_data, 'user_id_mapping', {})
        else:
            # 직접 딕셔너리인 경우
            data = workout_data
            user_id_mapping = {}
        
        # 1. 일별 운동 기록 업데이트 (배치 처리)
        print("🔄 일별 운동 기록 업데이트 중...")
        updated_records = 0
        
        # 업데이트할 레코드들을 수집
        update_data = []
        for date_key, user_data in data.items():
            for user_name in user_data.keys():
                # 실제 Discord ID 사용 (매핑이 있는 경우)
                user_id = user_id_mapping.get(user_name, str(hash(user_name)))  # 실제 ID 또는 해시 ID
                update_data.append((user_id, user_name, date_key))
        
        # 배치 크기로 나누어서 처리 (한 번에 5개씩)
        batch_size = 5
        for i in range(0, len(update_data), batch_size):
            batch = update_data[i:i + batch_size]
            
            # 배치 내에서 비동기 처리
            tasks = []
            for user_id, user_name, date_key in batch:
                task = asyncio.get_event_loop().run_in_executor(
                    None, upsert_daily_workout_record, user_id, user_name, date_key, client
                )
                tasks.append((task, user_name, user_id, date_key))
            
            # 배치 완료 대기
            for task, user_name, user_id, date_key in tasks:
                try:
                    success = await task
                    if success:
                        updated_records += 1
                        print(f"   ✅ 일별 기록 업데이트: {user_name} (ID: {user_id}) - {date_key}")
                    else:
                        print(f"   ❌ 일별 기록 업데이트 실패: {user_name} - {date_key}")
                except Exception as e:
                    print(f"   ❌ 일별 기록 업데이트 오류: {user_name} - {date_key}: {e}")
            
            # 배치 사이에 Discord heartbeat 유지를 위한 대기
            await asyncio.sleep(0.1)
        
        print(f"📊 일별 운동 기록 업데이트 완료: {updated_records}개")
        
        # Discord heartbeat 유지
        await asyncio.sleep(0.1)
        
        # 2. 주간 집계 업데이트 (비동기 실행)
        print("🔄 주간 집계 업데이트 중...")
        weekly_success = await asyncio.get_event_loop().run_in_executor(
            None, upsert_weekly_workout_records, client
        )
        if weekly_success:
            print("✅ 주간 집계 업데이트 완료")
        else:
            print("❌ 주간 집계 업데이트 실패")
        
        # Discord heartbeat 유지
        await asyncio.sleep(0.1)
        
        # 3. 월간 집계 업데이트 (비동기 실행)
        print("🔄 월간 집계 업데이트 중...")
        monthly_success = await asyncio.get_event_loop().run_in_executor(
            None, upsert_monthly_workout_records, client
        )
        if monthly_success:
            print("✅ 월간 집계 업데이트 완료")
        else:
            print("❌ 월간 집계 업데이트 실패")
        
        # Discord heartbeat 유지
        await asyncio.sleep(0.1)
        
        # 4. 멤버 통계 업데이트 (비동기 실행)
        print("🔄 멤버 통계 업데이트 중...")
        stats_success = await asyncio.get_event_loop().run_in_executor(
            None, update_member_statistics, client
        )
        if stats_success:
            print("✅ 멤버 통계 업데이트 완료")
        else:
            print("❌ 멤버 통계 업데이트 실패")
        
        overall_success = updated_records > 0 and weekly_success and monthly_success and stats_success
        
        if overall_success:
            print("🎉 모든 데이터베이스 업데이트 완료!")
            await send_alert_to_channel(
                client, 
                f"운동 스레드 분석 완료: {updated_records}개 일별 기록 업데이트, 주간/월간 집계 및 멤버 통계 갱신", 
                "Success", 
                "!동기화 명령어 - 데이터베이스 업데이트"
            )
        else:
            print("⚠️ 일부 데이터베이스 업데이트 실패")
            await send_alert_to_channel(
                client, 
                f"운동 스레드 분석 부분 실패: 일별 기록 {updated_records}개, 주간집계: {weekly_success}, 월간집계: {monthly_success}, 통계: {stats_success}", 
                "Warning", 
                "!동기화 명령어 - 데이터베이스 업데이트"
            )
        
        return overall_success
        
    except Exception as e:
        error_msg = f"데이터베이스 업데이트 중 오류: {e}"
        print(f"❌ {error_msg}")
        await send_error_to_error_channel(
            client, 
            error_msg, 
            type(e).__name__, 
            "update_database_with_workout_data",
            "시스템"
        )
        return False


async def calculate_user_workout_from_threads(client, start_date, end_date):
    """
    지정된 기간의 운동 스레드에서 사용자별 사진 업로드 현황을 계산하는 함수
    
    Args:
        client: Discord 클라이언트
        start_date: 시작 날짜 (datetime.date)
        end_date: 종료 날짜 (datetime.date, 포함)
        
    Returns:
        dict: {
            'workout_data': {날짜: {사용자: 사진_개수}},
            'total_threads_found': int,
            'total_photos_found': int,
            'user_totals': {사용자: 총_업로드_일수},
            'user_id_mapping': {사용자명: discord_id}
        }
    """
    try:
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            print(f"❌ 채널 ID {DISCORD_CHANNEL_ID}를 찾을 수 없습니다.")
            return None
        
        # 결과 데이터 초기화
        workout_data = {}
        total_threads_found = 0
        total_photos_found = 0
        user_id_mapping = {}  # 전체 사용자 ID 매핑
        
        # 수집할 날짜 범위 계산
        current_date = start_date
        target_dates = []
        
        while current_date <= end_date:
            target_dates.append(current_date)
            workout_data[current_date.strftime('%Y-%m-%d')] = {}
            current_date += timedelta(days=1)
        
        print(f"🔍 채널 '{channel.name}'에서 운동 스레드 사진 수집 시작...")
        print(f"📅 수집 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
        print(f"📋 수집 대상 날짜: {[date.strftime('%Y-%m-%d') for date in target_dates]}")
        
        # 활성 스레드에서 운동 스레드 찾기
        print("🔍 활성 스레드 검색 중...")
        active_count = 0
        for thread in channel.threads:
            thread_data = await _process_workout_thread(thread, target_dates)
            if thread_data:
                total_threads_found += 1
                total_photos_found += thread_data['photo_count']
                workout_data[thread_data['date_key']].update(thread_data['user_data'])
                user_id_mapping.update(thread_data['user_id_mapping'])
                active_count += 1
        print(f"📊 활성 스레드에서 {active_count}개 운동 스레드 발견")
        
        # 보관된 스레드에서도 찾기 (더 포괄적으로)
        print("🔍 보관된 스레드 검색 중...")
        archived_count = 0
        try:
            # 더 오래된 스레드까지 찾기 위해 여러 번 조회
            before_timestamp = None
            max_iterations = 10  # 최대 10번 반복 (안전장치)
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                found_in_this_batch = False
                
                # 공개 보관 스레드 조회 (페이지네이션)
                async for thread in channel.archived_threads(limit=100, before=before_timestamp, private=False):
                    thread_data = await _process_workout_thread(thread, target_dates)
                    if thread_data:
                        total_threads_found += 1
                        total_photos_found += thread_data['photo_count']
                        workout_data[thread_data['date_key']].update(thread_data['user_data'])
                        user_id_mapping.update(thread_data['user_id_mapping'])
                        archived_count += 1
                        found_in_this_batch = True
                    
                    # 다음 배치를 위해 타임스탬프 업데이트
                    before_timestamp = thread.created_at
                
                # 이번 배치에서 매칭되는 스레드가 없으면 중단
                if not found_in_this_batch:
                    break
                    
                print(f"  📦 배치 {iteration}: {archived_count}개 운동 스레드 발견 중...")
            
            # 비공개 보관 스레드도 조회 (권한이 있는 경우)
            try:
                before_timestamp = None
                iteration = 0
                while iteration < max_iterations:
                    iteration += 1
                    found_in_this_batch = False
                    
                    async for thread in channel.archived_threads(limit=100, before=before_timestamp, private=True):
                        thread_data = await _process_workout_thread(thread, target_dates)
                        if thread_data:
                            total_threads_found += 1
                            total_photos_found += thread_data['photo_count']
                            workout_data[thread_data['date_key']].update(thread_data['user_data'])
                            user_id_mapping.update(thread_data['user_id_mapping'])
                            archived_count += 1
                            found_in_this_batch = True
                        
                        before_timestamp = thread.created_at
                    
                    if not found_in_this_batch:
                        break
                        
            except discord.Forbidden:
                print("ℹ️ 비공개 보관 스레드 접근 권한이 없습니다.")
                
        except discord.Forbidden:
            print("⚠️ 보관된 스레드에 접근할 권한이 없습니다.")
        except Exception as e:
            print(f"⚠️ 보관된 스레드 조회 중 오류: {e}")
        
        print(f"📊 보관된 스레드에서 {archived_count}개 운동 스레드 발견")
        
        # 사용자별 총 업로드 횟수 계산
        user_totals = {}
        for date_data in workout_data.values():
            for user_name in date_data:
                user_totals[user_name] = user_totals.get(user_name, 0) + 1
        
        print(f"✅ 운동 스레드 사진 수집 완료!")
        print(f"📊 총 {total_threads_found}개 스레드에서 {total_photos_found}개 사진 발견")
        print(f"👥 총 {len(user_id_mapping)}명의 사용자 ID 매핑 수집")
        
        return {
            'workout_data': workout_data,
            'total_threads_found': total_threads_found,
            'total_photos_found': total_photos_found,
            'user_totals': user_totals,
            'user_id_mapping': user_id_mapping
        }
        
    except Exception as e:
        print(f"❌ 운동 스레드 사진 수집 중 오류: {e}")
        return None


async def _process_workout_thread(thread, target_dates):
    """
    단일 스레드가 운동 스레드인지 확인하고 사진 수집
    
    Args:
        thread: Discord 스레드
        target_dates: 대상 날짜 리스트 (datetime.date)
        
    Returns:
        dict or None: {
            'date_key': str,
            'user_data': {사용자: 1},
            'photo_count': int,
            'user_id_mapping': {사용자명: discord_id}
        }
    """
    try:
        thread_name = thread.name
        
        # 디버깅: 모든 스레드 이름 출력 (필요한 경우만)
        if len(target_dates) <= 10:  # 적은 날짜 범위일 때만 디버깅
            print(f"🔍 스레드 검사 중: '{thread_name}'")
        
        # 운동 스레드 패턴 확인 (예: "10월 31일 목", "7월 13일 목" 등)
        for target_date in target_dates:
            # 월, 일에서 앞의 0 제거 (7월 13일 형식으로 매칭)
            month = target_date.month
            day = target_date.day
            date_str = f"{month}월 {day}일"
            
            weekdays = ['월', '화', '수', '목', '금', '토', '일']
            weekday = weekdays[target_date.weekday()]
            expected_name = f"{date_str} {weekday}"
            
            # 다양한 패턴으로 매칭 시도
            patterns_to_check = [
                expected_name,  # "7월 13일 목"
                f"{month:02d}월 {day}일 {weekday}",  # "07월 13일 목" (0 포함)
                f"{month}월 {day:02d}일 {weekday}",  # "7월 13일 목" (일에만 0)
                f"{month:02d}월 {day:02d}일 {weekday}"  # "07월 13일 목" (둘 다 0)
            ]
            
            for pattern in patterns_to_check:
                if pattern in thread_name:
                    print(f"🎯 운동 스레드 발견: '{thread_name}' (패턴: '{pattern}', 날짜: {target_date.strftime('%Y-%m-%d')})")
                    
                    # 해당 스레드에서 사진 수집
                    user_data, photo_count, user_id_mapping = await _collect_photos_from_thread(thread, target_date.strftime('%Y-%m-%d'))
                    
                    return {
                        'date_key': target_date.strftime('%Y-%m-%d'),
                        'user_data': user_data,
                        'photo_count': photo_count,
                        'user_id_mapping': user_id_mapping
                    }
                    
            # 추가로 더 유연한 매칭 (날짜만 매칭, 요일 무시)
            date_only_patterns = [
                f"{month}월 {day}일",  # "7월 13일"
                f"{month:02d}월 {day}일",  # "07월 13일"
                f"{month}월 {day:02d}일",  # "7월 13일"
                f"{month:02d}월 {day:02d}일"  # "07월 13일"
            ]
            
            for date_pattern in date_only_patterns:
                if date_pattern in thread_name and any(wd in thread_name for wd in weekdays):
                    print(f"🎯 운동 스레드 발견 (유연한 매칭): '{thread_name}' (날짜: {target_date.strftime('%Y-%m-%d')})")
                    
                    # 해당 스레드에서 사진 수집
                    user_data, photo_count, user_id_mapping = await _collect_photos_from_thread(thread, target_date.strftime('%Y-%m-%d'))
                    
                    return {
                        'date_key': target_date.strftime('%Y-%m-%d'),
                        'user_data': user_data,
                        'photo_count': photo_count,
                        'user_id_mapping': user_id_mapping
                    }
                
    except Exception as e:
        print(f"⚠️ 스레드 '{thread.name}' 처리 중 오류: {e}")
    
    return None


async def _collect_photos_from_thread(thread, date_key):
    """
    특정 스레드에서 사용자별 사진 개수 수집
    
    Args:
        thread: Discord 스레드
        date_key: 날짜 키 (YYYY-MM-DD)
        
    Returns:
        tuple: (user_data, photo_count, user_id_mapping)
            user_data: {사용자명: 1}
            photo_count: int
            user_id_mapping: {사용자명: discord_id}
    """
    try:
        print(f"📥 스레드 '{thread.name}' ({date_key}) 사진 수집 중...")
        
        user_photos = {}  # {사용자_id: 사용자_이름}
        user_id_mapping = {}  # {사용자_이름: discord_id}
        photo_count = 0
        
        async for message in thread.history(limit=None):
            # 사진이 첨부된 메시지만 확인
            if message.attachments:
                # 이미지 파일인지 확인
                image_count = 0
                for attachment in message.attachments:
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        image_count += 1
                
                if image_count > 0:
                    user_id = message.author.id
                    
                    # 길드 멤버 정보를 통해 실제 이름 가져오기
                    try:
                        # 스레드가 속한 길드에서 멤버 정보 가져오기
                        guild = thread.guild
                        member = guild.get_member(user_id)
                        
                        if member:
                            # 1순위: 서버 닉네임 (display_name)
                            # 2순위: 글로벌 표시명 (global_name) 
                            # 3순위: 실제 유저명 (username)
                            user_name = member.display_name or message.author.global_name or message.author.name
                        else:
                            # 멤버 정보를 찾을 수 없는 경우 기본값 사용
                            user_name = message.author.display_name or message.author.global_name or message.author.name
                    except Exception as e:
                        print(f"   ⚠️ 멤버 정보 가져오기 실패 (ID: {user_id}): {e}")
                        user_name = message.author.name or message.author.global_name or message.author.display_name
                    
                    # 사용자별로 한 번만 카운팅 (같은 스레드에서 여러 사진 올려도 1번)
                    if user_id not in user_photos:
                        user_photos[user_id] = user_name
                        user_id_mapping[user_name] = str(user_id)  # Discord ID를 문자열로 저장
                        photo_count += 1
                        print(f"   📸 {user_name} (ID: {user_id}): 사진 발견 (총 {image_count}개 이미지)")
        
        # 결과 데이터 생성
        user_data = {user_name: 1 for user_name in user_photos.values()}
        
        print(f"📊 스레드 '{thread.name}' 완료: {len(user_photos)}명이 사진 업로드")
        
        return user_data, photo_count, user_id_mapping
        
    except Exception as e:
        print(f"❌ 스레드 '{thread.name}' 사진 수집 중 오류: {e}")
        return {}, 0, {}


# 운동 스레드 사진 수집기 클래스
class WorkoutThreadPhotoCollector:
    def __init__(self, client):
        self.client = client
        self.workout_data = {}  # {날짜: {사용자: 사진_개수}}
        self.total_threads_found = 0
        self.total_photos_found = 0
        self.user_id_mapping = {}  # {사용자명: discord_id}
        
    async def collect_workout_photos(self, days_back=7):
        """지정된 기간의 운동 스레드에서 사용자별 사진 업로드 개수를 수집"""
        try:
            # 날짜 범위 계산 (오늘부터 과거로)
            now = datetime.now(KST)
            today = now.date()
            start_date = today - timedelta(days=days_back-1)  # days_back일 전부터
            end_date = today  # 오늘까지
            
            # 새로운 함수 사용
            result = await calculate_user_workout_from_threads(self.client, start_date, end_date)
            
            if result:
                self.workout_data = result['workout_data']
                self.total_threads_found = result['total_threads_found']
                self.total_photos_found = result['total_photos_found']
                self.user_id_mapping = result['user_id_mapping']
                
                # 결과 출력
                self._print_results()
                
                return True
            else:
                return False
            
        except Exception as e:
            print(f"❌ 운동 스레드 사진 수집 중 오류: {e}")
            return False
    
    def _print_results(self):
        """수집 결과를 콘솔에 출력"""
        print("\n" + "="*80)
        print("📊 운동 스레드 사진 업로드 현황")
        print("="*80)
        
        total_users = set()
        
        for date_key in sorted(self.workout_data.keys(), reverse=True):
            date_data = self.workout_data[date_key]
            print(f"\n📅 {date_key} ({len(date_data)}명):")
            
            if date_data:
                for user_name, count in sorted(date_data.items()):
                    print(f"   📸 {user_name}: {count}회")
                    total_users.add(user_name)
            else:
                print(f"   ❌ 사진 업로드 없음")
        
        # 사용자별 총 업로드 횟수 계산
        user_totals = {}
        for date_data in self.workout_data.values():
            for user_name in date_data:
                user_totals[user_name] = user_totals.get(user_name, 0) + 1
        
        print(f"\n🏆 사용자별 총 업로드 횟수:")
        for user_name, total_count in sorted(user_totals.items(), key=lambda x: x[1], reverse=True):
            print(f"   📸 {user_name}: {total_count}일")
        
        print(f"\n📈 전체 요약:")
        print(f"   🎯 수집된 스레드 수: {self.total_threads_found}개")
        print(f"   📸 총 사진 업로드 횟수: {self.total_photos_found}회")
        print(f"   👥 참여한 사용자 수: {len(total_users)}명")
        print("="*80)
