import os
import json
import datetime
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 설정 ---
CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', '').strip()
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
README_PATH = "README.md"
START_DELIMITER = "<!-- CALENDAR:START -->"
END_DELIMITER = "<!-- CALENDAR:END -->"
# -------------

def get_calendar_service():
    """Google Calendar API 서비스 객체를 반환합니다."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS 환경 변수가 없습니다. GitHub Secret 확인 필요")
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service

def update_readme(markdown_content):
    """README.md 파일의 특정 섹션을 업데이트합니다."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()
    start_index = readme_content.find(START_DELIMITER)
    end_index = readme_content.find(END_DELIMITER)
    if start_index == -1 or end_index == -1:
        print(f"Error: Delimiters '{START_DELIMITER}' and/or '{END_DELIMITER}' not found in README.md")
        return
    before_content = readme_content[:start_index]
    after_content = readme_content[end_index + len(END_DELIMITER):]

    # [수정] 구분자도 다시 써 줘야 다음 실행에서 섹션을 찾을 수 있습니다.
    new_readme_content = (
        f"{before_content}{START_DELIMITER}\n"
        f"{markdown_content}\n"
        f"{END_DELIMITER}{after_content}"
    )

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme_content)

    print("README.md updated successfully!")

def generate_monthly_grid():
    """이번 달의 날짜가 담긴 2차원 리스트(주 단위)를 생성합니다."""
    # [수정] 표가 일요일부터 시작하므로, 데이터도 일요일부터 만들도록 설정합니다.
    calendar.setfirstweekday(calendar.SUNDAY)
    
    today = datetime.date.today()
    monthly_dates = calendar.monthcalendar(today.year, today.month)
    return monthly_dates, today.year, today.month

def get_monthly_events(service, calendar_id, year, month):
    """특정 월의 모든 이벤트를 가져옵니다."""
    _, last_day = calendar.monthrange(year, month)
    start_time = datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(year, month, last_day, 23, 59, 59, tzinfo=datetime.timezone.utc)
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        maxResults=250,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events

def create_markdown_calendar(monthly_grid, events, year, month):
    """날짜 그리드와 일정 데이터를 결합하여 마크다운 테이블을 생성합니다."""
    events_by_day = {}
    for event in events:
        start_str = event['start'].get('dateTime', event['start'].get('date'))
        # 타임존 정보가 없는 경우를 대비하여 예외 처리 추가
        try:
            start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        except ValueError:
            start_dt = datetime.datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
        
        day_num = start_dt.day
        if day_num not in events_by_day:
            events_by_day[day_num] = []
        summary = event.get('summary', '제목 없음')
        events_by_day[day_num].append(f"<sub>- {summary}</sub>")

    markdown = [f"### 🗓️ {year}년 {month}월 활동 기록 🗓️\n"]
    markdown.append("| Sun | Mon | Tue | Wed | Thu | Fri | Sat |")
    markdown.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for week in monthly_grid:
        week_row = "|"
        for day in week:
            if day == 0:
                week_row += " |"
            else:
                day_str = f"**{day}**"
                event_list_str = "<br>".join(events_by_day.get(day, []))
                week_row += f" {day_str}<br>{event_list_str} |"
        markdown.append(week_row)
    return "\n".join(markdown)

# --- 최종 실행 블록 ---
if __name__ == "__main__":
    # 1. 기본 뼈대(날짜 그리드) 생성
    monthly_grid, year, month = generate_monthly_grid()
    print(f"✅ Generated grid for {year}-{month}")

    # 2. API를 통해 캘린더 서비스 및 일정 데이터 가져오기
    service = get_calendar_service()
    events = get_monthly_events(service, CALENDAR_ID, year, month)
    print(f"✅ Fetched {len(events)} events from Google Calendar")

    # 3. 뼈대와 데이터를 합쳐 마크다운 캘린더 생성
    markdown_calendar = create_markdown_calendar(monthly_grid, events, year, month)
    print("✅ Created Markdown calendar")
    # print("\n--- Generated Markdown ---\n", markdown_calendar) # 결과 미리보기

    # 4. README 파일 업데이트
    update_readme(markdown_calendar)