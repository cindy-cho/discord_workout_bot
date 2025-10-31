"""
MySQL 데이터베이스 연결 모듈
운동 기록을 MySQL 데이터베이스에 저장하고 조회하는 기능을 제공합니다.
"""

import mysql.connector
from mysql.connector import Error
from datetime import datetime
import logging
import asyncio
from workout_bot_config import DATABASE_CONFIG

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkoutDatabase:
    def __init__(self):
        # config 파일에서 연결 정보 직접 가져오기
        self.host = DATABASE_CONFIG["host"]
        self.port = DATABASE_CONFIG["port"]
        self.database = DATABASE_CONFIG["database"]
        self.username = DATABASE_CONFIG["user"]
        self.password = DATABASE_CONFIG["password"]
        self.connection = None
        
    def connect(self):
        """MySQL 데이터베이스에 연결"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            
            if self.connection.is_connected():
                # 세션 타임존을 KST로 설정
                cursor = self.connection.cursor()
                cursor.execute("SET time_zone = '+09:00'")
                cursor.close()
                
                db_info = self.connection.get_server_info()
                logger.info(f"✅ MySQL 서버에 성공적으로 연결되었습니다. 버전: {db_info}")
                logger.info(f"📊 연결된 데이터베이스: {self.database}")
                logger.info("🕐 세션 타임존: +09:00 (KST)로 설정됨")
                return True
                
        except Error as e:
            error_msg = f"❌ MySQL 연결 오류: {e}"
            logger.error(error_msg)
            return False
    
    def disconnect(self):
        """MySQL 데이터베이스 연결 종료"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("🔌 MySQL 연결이 종료되었습니다.")
    
    def create_tables(self):
        """필요한 테이블들을 생성합니다"""
        if not self.connection or not self.connection.is_connected():
            logger.error("❌ 데이터베이스에 연결되지 않았습니다.")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 기존 테이블 삭제 (workout_records, weekly_stats)
            drop_tables = """
            DROP TABLE IF EXISTS workout_records;
            DROP TABLE IF EXISTS weekly_stats;
            """
            
            # 멤버 정보 테이블 생성
            create_members_table = """
            CREATE TABLE IF NOT EXISTS workout_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL UNIQUE,
                user_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_user_name (user_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 일별 운동 기록 테이블 (기존 유지하되 구조 정리)
            create_daily_workout_table = """
            CREATE TABLE IF NOT EXISTS daily_workout_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                weekday VARCHAR(10) NOT NULL,
                user_id VARCHAR(50) NOT NULL,
                user_name VARCHAR(255) NOT NULL,
                exercised CHAR(1) NOT NULL DEFAULT 'N',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_date (date, user_id),
                INDEX idx_date (date),
                INDEX idx_user_id (user_id),
                INDEX idx_weekday (weekday),
                FOREIGN KEY (user_id) REFERENCES workout_members(user_id) ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 주간 운동 기록 집계 테이블
            create_weekly_workout_table = """
            CREATE TABLE IF NOT EXISTS weekly_workout_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                user_name VARCHAR(255) NOT NULL,
                year INT NOT NULL,
                week_number INT NOT NULL,
                week_start_date DATE NOT NULL,
                week_end_date DATE NOT NULL,
                workout_days INT DEFAULT 0,
                workout_rate DECIMAL(5,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_week (user_id, year, week_number),
                INDEX idx_week_start (week_start_date),
                INDEX idx_user_week (user_id, year, week_number),
                FOREIGN KEY (user_id) REFERENCES workout_members(user_id) ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 월간 운동 기록 집계 테이블
            create_monthly_workout_table = """
            CREATE TABLE IF NOT EXISTS monthly_workout_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                user_name VARCHAR(255) NOT NULL,
                year INT NOT NULL,
                month INT NOT NULL,
                month_start_date DATE NOT NULL,
                month_end_date DATE NOT NULL,
                workout_days INT DEFAULT 0,
                total_days INT DEFAULT 0,
                workout_rate DECIMAL(5,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_month (user_id, year, month),
                INDEX idx_month_start (month_start_date),
                INDEX idx_user_month (user_id, year, month),
                FOREIGN KEY (user_id) REFERENCES workout_members(user_id) ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 테이블 삭제 실행
            for statement in drop_tables.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            
            # 새 테이블 생성 실행
            cursor.execute(create_members_table)
            cursor.execute(create_daily_workout_table)
            cursor.execute(create_weekly_workout_table)
            cursor.execute(create_monthly_workout_table)
            
            self.connection.commit()
            logger.info("✅ 테이블이 성공적으로 생성되었습니다.")
            logger.info("📋 생성된 테이블:")
            logger.info("   - workout_members (멤버 정보)")
            logger.info("   - daily_workout_records (일별 운동 기록)")
            logger.info("   - weekly_workout_records (주간 운동 집계)")
            logger.info("   - monthly_workout_records (월간 운동 집계)")
            return True
            
        except Error as e:
            logger.error(f"❌ 테이블 생성 오류: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def insert_workout_record(self, user_id, user_name, thread_id, thread_name, workout_date, attachment_count=0, message_content=""):
        """운동 기록을 데이터베이스에 삽입"""
        if not self.connection or not self.connection.is_connected():
            logger.error("❌ 데이터베이스에 연결되지 않았습니다.")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            insert_query = """
            INSERT INTO workout_records 
            (user_id, user_name, discord_thread_id, thread_name, workout_date, attachment_count, message_content)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (user_id, user_name, thread_id, thread_name, workout_date, attachment_count, message_content)
            cursor.execute(insert_query, values)
            
            self.connection.commit()
            record_id = cursor.lastrowid
            
            logger.info(f"✅ 운동 기록이 저장되었습니다. ID: {record_id}")
            logger.info(f"   👤 사용자: {user_name} (ID: {user_id})")
            logger.info(f"   📅 날짜: {workout_date}")
            logger.info(f"   🧵 스레드: {thread_name}")
            
            return record_id
            
        except Error as e:
            logger.error(f"❌ 운동 기록 저장 오류: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_user_workout_count(self, user_id, start_date=None, end_date=None):
        """특정 사용자의 운동 횟수를 조회"""
        if not self.connection or not self.connection.is_connected():
            logger.error("❌ 데이터베이스에 연결되지 않았습니다.")
            return 0
        
        try:
            cursor = self.connection.cursor()
            
            if start_date and end_date:
                query = """
                SELECT COUNT(*) FROM workout_records 
                WHERE user_id = %s AND workout_date BETWEEN %s AND %s
                """
                cursor.execute(query, (user_id, start_date, end_date))
            else:
                query = "SELECT COUNT(*) FROM workout_records WHERE user_id = %s"
                cursor.execute(query, (user_id,))
            
            result = cursor.fetchone()
            return result[0] if result else 0
            
        except Error as e:
            logger.error(f"❌ 운동 횟수 조회 오류: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
    
    def get_weekly_rankings(self, start_date, end_date):
        """주간 운동 랭킹을 조회"""
        if not self.connection or not self.connection.is_connected():
            logger.error("❌ 데이터베이스에 연결되지 않았습니다.")
            return []
        
        try:
            cursor = self.connection.cursor()
            
            query = """
            SELECT user_name, user_id, COUNT(*) as workout_count
            FROM workout_records 
            WHERE workout_date BETWEEN %s AND %s
            GROUP BY user_id, user_name
            ORDER BY workout_count DESC, user_name ASC
            """
            
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()
            
            rankings = []
            for row in results:
                rankings.append({
                    'user_name': row[0],
                    'user_id': row[1],
                    'workout_count': row[2]
                })
            
            return rankings
            
        except Error as e:
            logger.error(f"❌ 주간 랭킹 조회 오류: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def test_connection(self):
        """데이터베이스 연결 테스트"""
        if self.connect():
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                logger.info(f"🔍 MySQL 버전: {version[0]}")
                
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                logger.info(f"📋 데이터베이스 테이블 수: {len(tables)}")
                
                if tables:
                    logger.info("📝 존재하는 테이블:")
                    for table in tables:
                        logger.info(f"   - {table[0]}")
                
                return True
                
            except Error as e:
                logger.error(f"❌ 연결 테스트 오류: {e}")
                return False
            finally:
                if cursor:
                    cursor.close()
                self.disconnect()
        else:
            return False
    
    def calculate_current_streak_until_date(self, user_name, end_date):
        """
        특정 날짜까지의 현재 연속 운동일수를 계산합니다.
        
        Args:
            user_name (str): 사용자 이름
            end_date (date): 계산 기준 마지막 날짜 (포함)
            
        Returns:
            int: 연속 운동일수
        """
        if not self.connection or not self.connection.is_connected():
            logger.error("❌ 데이터베이스에 연결되지 않았습니다.")
            return 0
        
        try:
            cursor = self.connection.cursor()
            
            # end_date부터 역순으로 운동 기록을 조회
            query = """
            SELECT date 
            FROM daily_workout_records 
            WHERE user_name = %s AND date <= %s
            ORDER BY date DESC
            """
            
            cursor.execute(query, (user_name, end_date.strftime('%Y-%m-%d')))
            workout_dates = [row[0] for row in cursor.fetchall()]
            
            if not workout_dates:
                cursor.close()
                return 0
            
            # 연속 운동일수 계산
            from datetime import timedelta
            streak = 0
            current_date = end_date
            
            for workout_date in workout_dates:
                # 문자열인 경우 date 객체로 변환
                if isinstance(workout_date, str):
                    from datetime import datetime
                    workout_date = datetime.strptime(workout_date, '%Y-%m-%d').date()
                
                if workout_date == current_date:
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
            
            cursor.close()
            return streak
            
        except Error as e:
            logger.error(f"❌ 연속 운동일수 계산 중 오류: {e}")
            return 0


def calculate_user_workout_streak(client, user_name, end_date=None):
    """
    사용자의 연속 운동일수를 계산하는 독립 함수 (Discord 알림 포함)
    
    Args:
        client: Discord 클라이언트 객체
        user_name (str): 사용자 이름
        end_date (date, optional): 계산 기준 마지막 날짜. None이면 오늘 날짜 사용
        
    Returns:
        int: 연속 운동일수
    """
    try:
        # 데이터베이스 연결
        conn = get_database_connection(client)
        if not conn:
            logger.error("❌ 데이터베이스 연결 실패")
            return 0
            
        cursor = conn.cursor()
        
        # end_date가 없으면 오늘 날짜 사용
        if end_date is None:
            from datetime import date
            end_date = date.today()
        
        # end_date부터 역순으로 운동 기록을 조회
        query = """
        SELECT date 
        FROM daily_workout_records 
        WHERE user_name = %s AND date <= %s
        ORDER BY date DESC
        """
        
        cursor.execute(query, (user_name, end_date.strftime('%Y-%m-%d')))
        workout_dates = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        if not workout_dates:
            return 0
        
        # 연속 운동일수 계산
        from datetime import timedelta
        streak = 0
        current_date = end_date
        
        for workout_date in workout_dates:
            # 문자열인 경우 date 객체로 변환
            if isinstance(workout_date, str):
                from datetime import datetime
                workout_date = datetime.strptime(workout_date, '%Y-%m-%d').date()
            
            if workout_date == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        logger.info(f"📈 {user_name}님의 {end_date}까지 연속 운동일수: {streak}일")
        return streak
        
    except Exception as e:
        error_msg = f"연속 운동일수 계산 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        # Discord 알림
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        return 0

# 사용 예시
if __name__ == "__main__":
    # 데이터베이스 연결 테스트
    db = WorkoutDatabase()
    
    print("🔗 MySQL 데이터베이스 연결 테스트를 시작합니다...")
    
    if db.test_connection():
        print("✅ 데이터베이스 연결 테스트 성공!")
        
        # 테이블 생성 테스트
        if db.connect():
            db.create_tables()
            
            # 샘플 데이터 삽입 테스트
            sample_date = datetime.now().date()
            record_id = db.insert_workout_record(
                user_id=1234567890,
                user_name="테스트유저",
                thread_id=9876543210,
                thread_name="1월 1일 월",
                workout_date=sample_date,
                attachment_count=2,
                message_content="오늘 운동 완료!"
            )
            
            if record_id:
                print(f"✅ 샘플 데이터 삽입 성공! 레코드 ID: {record_id}")
                
                # 운동 횟수 조회 테스트
                count = db.get_user_workout_count(1234567890)
                print(f"📊 테스트유저의 총 운동 횟수: {count}회")
            
            db.disconnect()
    else:
        print("❌ 데이터베이스 연결 테스트 실패!")
        print("💡 연결 정보를 확인해주세요.")

def get_database_connection(client=None):
    """
    간단한 데이터베이스 연결 함수
    매번 새로운 연결을 생성하므로 사용 후 반드시 연결을 닫아야 합니다.
    
    Args:
        client: Discord 클라이언트 객체 (에러 알림을 위해 선택적으로 전달)
    
    Returns:
        mysql.connector.connection.MySQLConnection: 데이터베이스 연결 객체
        None: 연결 실패 시
    """
    try:
        connection = mysql.connector.connect(
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            database=DATABASE_CONFIG["database"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        if connection.is_connected():
            # 세션 타임존을 KST로 설정
            cursor = connection.cursor()
            cursor.execute("SET time_zone = '+09:00'")
            cursor.close()
            return connection
        else:
            error_msg = "❌ 데이터베이스 연결에 실패했습니다."
            logger.error(error_msg)
            # Discord 알림을 위한 비동기 함수 호출 (클라이언트가 있는 경우에만)
            if client:
                asyncio.create_task(send_database_error_alert(client, error_msg))
            return None
            
    except Error as e:
        error_msg = f"❌ 데이터베이스 연결 중 오류 발생: {e}"
        logger.error(error_msg)
        # Discord 알림을 위한 비동기 함수 호출 (클라이언트가 있는 경우에만)
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        return None


def upsert_daily_workout_record(user_id, user_name, workout_date, client=None):
    """
    일별 운동 기록을 UPSERT (INSERT OR UPDATE)하는 함수
    
    Args:
        user_id: 사용자 Discord ID (문자열)
        user_name: 사용자 이름
        workout_date: 운동 날짜 (datetime.date 또는 문자열)
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        bool: 성공 여부
    """
    conn = None
    cursor = None
    try:
        # 날짜 처리
        if isinstance(workout_date, str):
            from datetime import datetime
            workout_date = datetime.strptime(workout_date, '%Y-%m-%d').date()
        
        # 요일 계산
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        weekday = weekdays[workout_date.weekday()]
        
        # 데이터베이스 연결
        conn = get_database_connection(client)
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 먼저 workout_members에 사용자가 있는지 확인하고 없으면 추가
        member_check_query = "SELECT user_id FROM workout_members WHERE user_id = %s"
        cursor.execute(member_check_query, (user_id,))
        
        if not cursor.fetchone():
            # 사용자 추가
            insert_member_query = """
            INSERT INTO workout_members (user_id, user_name) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE user_name = VALUES(user_name)
            """
            cursor.execute(insert_member_query, (user_id, user_name))
            logger.info(f"✅ 새 멤버 추가: {user_name} (ID: {user_id})")
        
        # daily_workout_records UPSERT
        upsert_daily_query = """
        INSERT INTO daily_workout_records 
        (date, weekday, user_id, user_name, exercised)
        VALUES (%s, %s, %s, %s, 'Y')
        ON DUPLICATE KEY UPDATE 
            exercised = 'Y',
            user_name = VALUES(user_name),
            updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.execute(upsert_daily_query, (workout_date, weekday, user_id, user_name))
        
        conn.commit()
        logger.info(f"✅ 일별 운동 기록 업데이트: {user_name} - {workout_date}")
        return True
        
    except Exception as e:
        error_msg = f"일별 운동 기록 UPSERT 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def upsert_weekly_workout_records(client=None):
    """
    daily_workout_records를 기반으로 weekly_workout_records를 업데이트하는 함수
    
    Args:
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        bool: 성공 여부
    """
    conn = None
    cursor = None
    try:
        conn = get_database_connection(client)
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 최근 4주간의 주간 집계 업데이트
        weekly_upsert_query = """
        INSERT INTO weekly_workout_records 
        (user_id, user_name, year, week_number, week_start_date, week_end_date, workout_days, workout_rate)
        SELECT 
            user_id,
            user_name,
            YEAR(date) as year,
            WEEK(date, 1) as week_number,
            DATE_SUB(date, INTERVAL WEEKDAY(date) DAY) as week_start_date,
            DATE_ADD(DATE_SUB(date, INTERVAL WEEKDAY(date) DAY), INTERVAL 6 DAY) as week_end_date,
            COUNT(DISTINCT date) as workout_days,
            ROUND((COUNT(DISTINCT date) / 7.0) * 100, 2) as workout_rate
        FROM daily_workout_records 
        WHERE exercised = 'Y' 
            AND date >= DATE_SUB(CURDATE(), INTERVAL 4 WEEK)
        GROUP BY user_id, user_name, YEAR(date), WEEK(date, 1)
        ON DUPLICATE KEY UPDATE
            workout_days = VALUES(workout_days),
            workout_rate = VALUES(workout_rate),
            week_start_date = VALUES(week_start_date),
            week_end_date = VALUES(week_end_date),
            user_name = VALUES(user_name),
            updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.execute(weekly_upsert_query)
        affected_rows = cursor.rowcount
        
        conn.commit()
        logger.info(f"✅ 주간 운동 기록 업데이트 완료: {affected_rows}개 레코드")
        return True
        
    except Exception as e:
        error_msg = f"주간 운동 기록 UPSERT 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def upsert_monthly_workout_records(client=None):
    """
    daily_workout_records를 기반으로 monthly_workout_records를 업데이트하는 함수
    
    Args:
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        bool: 성공 여부
    """
    conn = None
    cursor = None
    try:
        conn = get_database_connection(client)
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 최근 3개월간의 월간 집계 업데이트
        monthly_upsert_query = """
        INSERT INTO monthly_workout_records 
        (user_id, user_name, year, month, month_start_date, month_end_date, workout_days, total_days, workout_rate)
        SELECT 
            user_id,
            user_name,
            YEAR(date) as year,
            MONTH(date) as month,
            DATE_FORMAT(date, '%Y-%m-01') as month_start_date,
            LAST_DAY(date) as month_end_date,
            COUNT(DISTINCT date) as workout_days,
            DAY(LAST_DAY(date)) as total_days,
            ROUND((COUNT(DISTINCT date) / DAY(LAST_DAY(date))) * 100, 2) as workout_rate
        FROM daily_workout_records 
        WHERE exercised = 'Y' 
            AND date >= DATE_SUB(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 2 MONTH)
        GROUP BY user_id, user_name, YEAR(date), MONTH(date)
        ON DUPLICATE KEY UPDATE
            workout_days = VALUES(workout_days),
            total_days = VALUES(total_days),
            workout_rate = VALUES(workout_rate),
            month_start_date = VALUES(month_start_date),
            month_end_date = VALUES(month_end_date),
            user_name = VALUES(user_name),
            updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.execute(monthly_upsert_query)
        affected_rows = cursor.rowcount
        
        conn.commit()
        logger.info(f"✅ 월간 운동 기록 업데이트 완료: {affected_rows}개 레코드")
        return True
        
    except Exception as e:
        error_msg = f"월간 운동 기록 UPSERT 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def update_member_statistics(client=None):
    """
    workout_members 테이블의 통계 정보를 업데이트하는 함수
    
    Args:
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        bool: 성공 여부
    """
    conn = None
    cursor = None
    try:
        conn = get_database_connection(client)
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # workout_members 테이블에 통계 컬럼이 있는지 확인하고 없으면 추가
        add_columns_query = """
        ALTER TABLE workout_members 
        ADD COLUMN IF NOT EXISTS total_workout_days INT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS total_days INT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS workout_rate DECIMAL(5,2) DEFAULT 0.00,
        ADD COLUMN IF NOT EXISTS current_streak INT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS max_streak INT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_workout_date DATE DEFAULT NULL
        """
        
        try:
            cursor.execute(add_columns_query)
        except Exception as column_error:
            # 컬럼이 이미 존재하는 경우 무시
            logger.info(f"컬럼 추가 건너뜀: {column_error}")
        
        # 각 멤버의 통계 업데이트
        update_stats_query = """
        UPDATE workout_members wm
        JOIN (
            SELECT 
                user_id,
                COUNT(DISTINCT date) as total_workout_days,
                DATEDIFF(CURDATE(), MIN(date)) + 1 as total_days,
                ROUND((COUNT(DISTINCT date) / (DATEDIFF(CURDATE(), MIN(date)) + 1)) * 100, 2) as workout_rate,
                MAX(date) as last_workout_date
            FROM daily_workout_records 
            WHERE exercised = 'Y'
            GROUP BY user_id
        ) stats ON wm.user_id = stats.user_id
        SET 
            wm.total_workout_days = stats.total_workout_days,
            wm.total_days = stats.total_days,
            wm.workout_rate = stats.workout_rate,
            wm.last_workout_date = stats.last_workout_date,
            wm.updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.execute(update_stats_query)
        
        # 연속 운동일수 계산 및 업데이트 (각 사용자별로 개별 계산)
        cursor.execute("SELECT user_id, user_name FROM workout_members")
        members = cursor.fetchall()
        
        for user_id, user_name in members:
            current_streak = calculate_current_streak_for_user(user_id, user_name, client)
            max_streak = calculate_max_streak_for_user(user_id, user_name, client)
            
            cursor.execute("""
                UPDATE workout_members 
                SET current_streak = %s, max_streak = %s 
                WHERE user_id = %s
            """, (current_streak, max_streak, user_id))
        
        conn.commit()
        logger.info(f"✅ 멤버 통계 업데이트 완료: {len(members)}명")
        return True
        
    except Exception as e:
        error_msg = f"멤버 통계 업데이트 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def calculate_current_streak_for_user(user_id, user_name, client=None):
    """
    사용자의 현재 연속 운동일수를 계산하는 함수 (오늘 기준)
    
    Args:
        user_id: 사용자 ID
        user_name: 사용자 이름  
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        int: 현재 연속 운동일수
    """
    conn = None
    cursor = None
    try:
        from datetime import datetime, timedelta
        import pytz
        
        # 한국 시간 기준으로 어제 날짜 계산 (연속일수는 어제까지 기준)
        KST = pytz.timezone('Asia/Seoul')
        now = datetime.now(KST)
        yesterday = (now - timedelta(days=1)).date()
        
        conn = get_database_connection(client)
        if not conn:
            return 0
        
        cursor = conn.cursor()
        
        # 어제부터 역순으로 운동 기록을 조회
        query = """
        SELECT date 
        FROM daily_workout_records 
        WHERE user_id = %s AND exercised = 'Y' AND date <= %s
        ORDER BY date DESC
        """
        
        cursor.execute(query, (user_id, yesterday.strftime('%Y-%m-%d')))
        workout_dates = [row[0] for row in cursor.fetchall()]
        
        if not workout_dates:
            return 0
        
        # 연속 운동일수 계산
        streak = 0
        current_date = yesterday
        
        for workout_date in workout_dates:
            # 문자열인 경우 date 객체로 변환
            if isinstance(workout_date, str):
                workout_date = datetime.strptime(workout_date, '%Y-%m-%d').date()
            
            if workout_date == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        logger.info(f"📈 {user_name}님의 현재 연속 운동일수: {streak}일 (기준일: {yesterday})")
        return streak
        
    except Exception as e:
        error_msg = f"현재 연속 운동일수 계산 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        return 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def calculate_max_streak_for_user(user_id, user_name, client=None):
    """
    사용자의 최장 연속 운동일수를 계산하는 함수
    
    Args:
        user_id: 사용자 ID
        user_name: 사용자 이름  
        client: Discord 클라이언트 (에러 알림용, 선택사항)
    
    Returns:
        int: 최장 연속 운동일수
    """
    conn = None
    cursor = None
    try:
        conn = get_database_connection(client)
        if not conn:
            return 0
        
        cursor = conn.cursor()
        
        # 해당 사용자의 모든 운동 날짜를 오름차순으로 조회
        query = """
        SELECT date FROM daily_workout_records 
        WHERE user_id = %s AND exercised = 'Y' 
        ORDER BY date ASC
        """
        
        cursor.execute(query, (user_id,))
        workout_dates = [row[0] for row in cursor.fetchall()]
        
        if not workout_dates:
            return 0
        
        # 최장 연속일수 계산
        from datetime import timedelta
        max_streak = 1
        current_streak = 1
        
        for i in range(1, len(workout_dates)):
            # 날짜 차이가 1일인지 확인
            date_diff = (workout_dates[i] - workout_dates[i-1]).days
            
            if date_diff == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        logger.info(f"📈 {user_name}님의 최장 연속 운동일수: {max_streak}일")
        return max_streak
        
    except Exception as e:
        error_msg = f"최장 연속 운동일수 계산 중 오류: {e}"
        logger.error(f"❌ {error_msg}")
        if client:
            asyncio.create_task(send_database_error_alert(client, error_msg))
        return 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def send_database_error_alert(client, error_message):
    """
    데이터베이스 에러 발생 시 Discord 채널에 알림을 보내는 함수
    
    Args:
        client: Discord 클라이언트 객체
        error_message: 에러 메시지
    """
    try:
        # workout_bot_commands에서 send_alert_to_channel 함수를 import
        from workout_bot_commands import send_alert_to_channel
        
        await send_alert_to_channel(
            client, 
            error_message, 
            "Database Error", 
            "workout_bot_database.py - Database Connection"
        )
    except Exception as alert_error:
        logger.error(f"❌ Discord 알림 전송 실패: {alert_error}")
