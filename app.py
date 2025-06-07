import streamlit as st
import sqlite3
import bcrypt
import os
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import datetime
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# --- 기본 설정 및 초기화 ---
st.set_page_config(layout="wide")

# 세션 상태에 위치 정보 저장
if 'location' not in st.session_state:
    st.session_state.location = None

# 환경변수 로드
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
DB_PATH = os.getenv('DB_PATH', './app.db')

# --- 데이터베이스 함수 ---
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, creator TEXT NOT NULL,
            duration INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL,
            name TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def delete_expired_rooms():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, created_at, duration FROM rooms")
    for room in c.fetchall():
        created_dt = datetime.datetime.fromisoformat(room['created_at'])
        expire_dt = created_dt + datetime.timedelta(minutes=room['duration'])
        if datetime.datetime.now() > expire_dt:
            c.execute("DELETE FROM rooms WHERE id = ?", (room['id'],))
    conn.commit()
    conn.close()

# --- 세션 상태 초기화 ---
if 'current_room' not in st.session_state:
    st.session_state.current_room = None

# --- 앱 초기 실행 ---
init_db()
delete_expired_rooms()

# --- UI 렌더링 함수 ---

def render_main_view():
    st.sidebar.title("위치 공유 앱")
    
    # 위치 정보 요청 및 처리
    col1, col2 = st.columns([1, 3])
    with col1:
        loc_button = st.button("내 위치 가져오기 🎯")
    
    if loc_button:
        js_code = """
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const pos = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                window.parent.postMessage({
                    type: "streamlit:set_location",
                    location: pos
                }, "*");
            },
            function(error) {
                console.error("위치 정보 획득 실패:", error);
                window.parent.postMessage({
                    type: "streamlit:location_error",
                    error: error.message
                }, "*");
            },
            {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }
        );
        """
        streamlit_js_eval(js_code=js_code)
        
    user_location = get_geolocation()
    if user_location:
        st.session_state.location = user_location
        
    # 위치 정보 표시
    if st.session_state.location:
        st.success(f"현재 위치: 위도 {st.session_state.location['latitude']:.6f}, 경도 {st.session_state.location['longitude']:.6f}")
    
    # --- 사이드바: 방 생성 ---
    with st.sidebar.expander("새로운 방 만들기"):
        with st.form("create_room_form"):
            room_name = st.text_input("방 이름")
            password = st.text_input("비밀번호", type="password")
            creator = st.text_input("생성자 이름")
            duration = st.number_input("지속 시간(분)", min_value=1, value=60)
            create_submitted = st.form_submit_button("만들기")

            if create_submitted:
                if not (room_name and password and creator):
                    st.warning("모든 필드를 입력하세요.")
                else:
                    try:
                        conn = get_conn()
                        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                        conn.execute('INSERT INTO rooms (name, password_hash, creator, duration) VALUES (?, ?, ?, ?)',
                                     (room_name, password_hash, creator, duration))
                        conn.commit()
                        st.success(f"방 '{room_name}'이 생성되었습니다.")
                    except sqlite3.IntegrityError:
                        st.error("이미 존재하는 방 이름입니다.")
                    finally:
                        conn.close()

    # --- 사이드바: 방 목록 및 참가 ---
    st.sidebar.header("참가 가능한 방")
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY created_at DESC").fetchall()
    conn.close()

    if not rooms:
        st.sidebar.info("참가 가능한 방이 없습니다.")
    
    join_room_id_to_process = None
    for room in rooms:
        if st.sidebar.button(f"🚪 {room['name']}", key=f"room_{room['id']}"):
            if user_location:
                st.session_state.join_room_id = room['id']
                join_room_id_to_process = room['id']
            else:
                st.sidebar.error("방에 참가하려면 먼저 브라우저의 위치 권한을 허용하고 페이지를 새로고침 해주세요.")
                st.session_state.join_room_id = None # Clear any previous selection

    if 'join_room_id' in st.session_state and st.session_state.join_room_id:
        render_join_form(user_location)

    # --- 메인 화면: 지도 표시 ---
    st.header("내 위치 및 주변 탐색")

    # 위치 정보 유효성 검사 강화
    has_location = st.session_state.location and isinstance(st.session_state.location, dict) and 'latitude' in st.session_state.location

    if has_location:
        map_center = [st.session_state.location['latitude'], st.session_state.location['longitude']]
    else:
        map_center = [37.5665, 126.9780]  # 기본값: 서울
        st.info("'내 위치 가져오기' 버튼을 클릭하여 현재 위치를 확인하세요.")

    m = folium.Map(location=map_center, zoom_start=14)
    if has_location:
        folium.Marker(
            location=map_center,
            popup="내 현재 위치",
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    st_folium(m, use_container_width=True, height=500)

def render_join_form(user_location):
    # Double-check location exists before proceeding
    if not user_location:
        st.error("위치 정보를 가져올 수 없습니다. 참가를 다시 시도해주세요.")
        st.session_state.join_room_id = None
        return

    room_id = st.session_state.join_room_id
    conn = get_conn()
    room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    conn.close()

    st.sidebar.subheader(f"'{room['name']}' 방 참가")
    with st.sidebar.form("join_form"):
        participant_name = st.text_input("내 이름")
        join_password = st.text_input("방 비밀번호", type="password")
        join_submitted = st.form_submit_button("참가하기")

        if join_submitted:
            if not participant_name:
                st.warning("이름을 입력하세요.")
            elif not bcrypt.checkpw(join_password.encode(), room['password_hash'].encode()):
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                conn = get_conn()
                conn.execute('INSERT INTO participants (room_id, name, latitude, longitude) VALUES (?, ?, ?, ?)',
                             (room['id'], participant_name, user_location['latitude'], user_location['longitude']))
                conn.commit()
                conn.close()
                st.session_state.current_room = room
                del st.session_state.join_room_id
                st.rerun()

def render_in_room_view():
    room = st.session_state.current_room
    st_autorefresh(interval=5000, key="room_autorefresh")
    
    conn = get_conn()
    participants = conn.execute("SELECT * FROM participants WHERE room_id = ?", (room['id'],)).fetchall()
    conn.close()

    # --- 사이드바 ---
    st.sidebar.title(f"'{room['name']}' 방")
    st.sidebar.header("참가자 목록")
    for p in participants:
        st.sidebar.markdown(f"- **{p['name']}**")
    
    if st.sidebar.button("방 나가기"):
        st.session_state.current_room = None
        st.rerun()

    # --- 메인 화면: 참가자 지도 ---
    st.header(f"'{room['name']}' 참가자 위치")
    map_center = [participants[0]['latitude'], participants[0]['longitude']] if participants else [37.5665, 126.9780]
    m = folium.Map(location=map_center, zoom_start=14)
    for p in participants:
        folium.Marker([p['latitude'], p['longitude']], popup=p['name']).add_to(m)
    
    st_folium(m, use_container_width=True, height=500, returned_objects=[])

# --- 메인 로직 라우터 ---
if st.session_state.current_room:
    render_in_room_view()
else:
    render_main_view() 