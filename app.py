import streamlit as st
import sqlite3
import bcrypt
import os
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import datetime
from streamlit_js_eval import get_geolocation

# 환경변수 로드
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
DB_PATH = os.getenv('DB_PATH', './app.db')

# DB 연결 및 테이블 생성
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            creator TEXT NOT NULL,
            duration INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES rooms(id)
        )
    ''')
    conn.commit()
    conn.close()

def delete_expired_rooms():
    now = datetime.datetime.now()
    conn = get_conn()
    c = conn.cursor()
    # 만료된 방 id 조회
    c.execute('SELECT id, created_at, duration FROM rooms')
    expired_ids = []
    for room_id, created_at, duration in c.fetchall():
        created_dt = datetime.datetime.fromisoformat(created_at)
        expire_dt = created_dt + datetime.timedelta(minutes=duration)
        if now > expire_dt:
            expired_ids.append(room_id)
    # 만료된 방 및 참가자 삭제
    for room_id in expired_ids:
        c.execute('DELETE FROM participants WHERE room_id = ?', (room_id,))
        c.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
    conn.commit()
    conn.close()

init_db()

# 앱 실행 시 만료 방 삭제
delete_expired_rooms()

# 자동 새로고침 (5초 간격)
st_autorefresh(interval=5000, key="autorefresh")

# 위치 자동 감지 (폼 바깥)
loc = get_geolocation()
if not (loc and loc.get('latitude') and loc.get('longitude')):
    st_autorefresh(interval=2000, key="geo_autorefresh")

# 방 생성 폼
st.title('위치 공유 방 생성')
with st.form('create_room'):
    room_name = st.text_input('방 이름')
    password = st.text_input('비밀번호', type='password')
    creator = st.text_input('생성자 이름')
    duration = st.number_input('지속 시간(분)', min_value=1, max_value=1440, value=60)
    submitted = st.form_submit_button('방 생성')

    if submitted:
        delete_expired_rooms()
        if not (room_name and password and creator):
            st.warning('모든 항목을 입력하세요.')
        else:
            # 비밀번호 해시
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn = get_conn()
            c = conn.cursor()
            c.execute('INSERT INTO rooms (name, password_hash, creator, duration) VALUES (?, ?, ?, ?)',
                      (room_name, password_hash, creator, duration))
            conn.commit()
            conn.close()
            st.success(f'방 "{room_name}" 이(가) 생성되었습니다!')

st.header('방 참가')

st.warning(
    """
    **[중요] 위치 정보 사용법**

    1. 브라우저가 위치 권한을 요청하면 **'허용'**을 클릭해주세요.
    2. 권한 허용 후, **페이지를 직접 새로고침(F5 또는 브라우저 새로고침 버튼)** 해주세요.
    3. 아래에 "✅ 위치가 확인되었습니다" 메시지가 표시되면 참가를 진행할 수 있습니다.
    """
)

# 위치 자동 감지
loc = get_geolocation()

with st.form('join_room'):
    join_room_name = st.text_input('참가할 방 이름')
    join_password = st.text_input('방 비밀번호', type='password')
    participant_name = st.text_input('참가자 이름')

    # Display status but don't disable the button
    if loc and loc.get('latitude'):
        st.success(f"✅ 위치가 확인되었습니다: {loc['latitude']}, {loc['longitude']}")
    else:
        st.info("...위치 정보를 기다리는 중입니다. (권한 허용 후 페이지 새로고침 필요)")

    join_submitted = st.form_submit_button('방 참가')

    if join_submitted:
        # Check for location again upon submission
        if not (loc and loc.get('latitude')):
            st.error("❗ 위치 정보를 가져오지 못했습니다. 페이지를 새로고침한 후 다시 시도해주세요.")
        elif not (join_room_name and join_password and participant_name):
            st.warning("❗ 방 이름, 비밀번호, 참가자 이름을 모두 입력하세요.")
        else:
            # All good, proceed with submission
            latitude = loc['latitude']
            longitude = loc['longitude']

            delete_expired_rooms()
            
            conn = get_conn()
            c = conn.cursor()
            c.execute('SELECT id, password_hash FROM rooms WHERE name = ?', (join_room_name,))
            room = c.fetchone()
            if not room:
                st.error('해당 이름의 방이 존재하지 않습니다.')
            else:
                room_id, password_hash = room
                if not bcrypt.checkpw(join_password.encode(), password_hash.encode()):
                    st.error('비밀번호가 일치하지 않습니다.')
                else:
                    c.execute('INSERT INTO participants (room_id, name, latitude, longitude) VALUES (?, ?, ?, ?)',
                              (room_id, participant_name, latitude, longitude))
                    conn.commit()
                    st.success(f'{participant_name}님이 방 "{join_room_name}"에 참가하였습니다!')
            conn.close()
            st.rerun()

st.header('방 참가자 위치 보기')

# 방 이름 목록 불러오기
conn = get_conn()
c = conn.cursor()
c.execute('SELECT name FROM rooms')
room_names = [row[0] for row in c.fetchall()]
conn.close()

selected_room = st.selectbox('방 선택', room_names, key='view_room')

if selected_room:
    delete_expired_rooms()
    # 방 id 조회
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id FROM rooms WHERE name = ?', (selected_room,))
    room_row = c.fetchone()
    if room_row:
        room_id = room_row[0]
        # 참가자 정보 조회
        c.execute('SELECT name, latitude, longitude, joined_at FROM participants WHERE room_id = ?', (room_id,))
        participants = c.fetchall()
        conn.close()

        if participants:
            st.subheader('참가자 리스트')
            st.table([
                {'이름': name, '위도': lat, '경도': lon, '참가시각': joined_at}
                for name, lat, lon, joined_at in participants
            ])

            # 지도 중심: 첫 참가자 위치 또는 기본값
            map_center = [participants[0][1], participants[0][2]] if participants else [37.5665, 126.9780]
            m = folium.Map(location=map_center, zoom_start=13)
            for name, lat, lon, _ in participants:
                folium.Marker([lat, lon], popup=name).add_to(m)
            st_folium(m, width=700, height=500)
        else:
            st.info('이 방에는 아직 참가자가 없습니다.')
    else:
        st.warning('방 정보를 찾을 수 없습니다.') 