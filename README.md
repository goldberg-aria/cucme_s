# Streamlit 기반 위치 공유 웹앱 (SQLite 버전)

## 프로젝트 개요
- 실시간으로 방(Room)을 생성하고, 참가자들이 자신의 위치를 공유할 수 있는 웹앱입니다.
- Python, Streamlit, SQLite 기반으로 개발합니다.

## 주요 기능
1. **방 생성**
   - 방 이름, 비밀번호, 생성자 이름, 지속 시간 입력
   - SQLite DB에 방 정보 저장

2. **방 참가**
   - 방 이름, 비밀번호 입력 후 참가
   - 참가자 이름, 위치(위도/경도) 입력
   - 참가자 리스트 및 위치 지도에 표시

3. **위치 공유**
   - 참가자가 자신의 위치를 입력 및 공유
   - 지도(예: Folium) 위에 모든 참가자의 위치 마커 표시

4. **보안**
   - 비밀번호는 해시 처리하여 저장
   - 민감 정보는 .env 파일로 관리

5. **실시간 새로고침**
   - 참가자 리스트와 지도 자동 갱신(streamlit-autorefresh)

6. **방 만료**
   - 지속 시간 경과 시 방 및 참가자 정보 자동 삭제

## 기술 스택
- Python 3.9+
- Streamlit
- SQLite (Python 내장 sqlite3)
- streamlit-folium (지도 표시)
- bcrypt (비밀번호 해시)
- python-dotenv (환경변수 관리)
- streamlit-autorefresh (실시간 새로고침)

## 설치 및 실행 방법

1. 가상환경(venv) 생성 및 활성화
    ```bash
    # 가상환경 생성
    python3 -m venv venv

    # (macOS/Linux) 가상환경 활성화
    source venv/bin/activate

    # (Windows) 가상환경 활성화
    venv\Scripts\activate
    ```

2. 의존성 설치
    ```bash
    pip install -r requirements.txt
    ```

3. .env 파일 생성 (예시)
    ```
    DB_PATH=./app.db
    ```

4. 앱 실행
    ```bash
    streamlit run app.py
    ```

## 폴더 구조 예시
```
streamlit-location-share/
  app.py
  requirements.txt
  .env
  README.md
```

## 개발 가이드
- 기능별로 함수/클래스 분리
- 민감 정보는 코드에 직접 노출하지 않기
- 코드에 주석 및 문서화 철저히
- 테스트 코드 작성 권장

## 기여 방법
- 이슈/PR 등록 전 README 및 코드 컨벤션 확인 