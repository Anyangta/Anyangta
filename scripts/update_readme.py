import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 설정 ---
CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID') # GitHub Secret에서 가져옴
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') # GitHub Secret에서 생성된 파일 경로

README_PATH = "README.md"
START_DELIMITER = "<!-- START_CALENDAR -->"
END_DELIMITER = "<!-- END_CALENDAR -->"
# -------------

def get_calendar_service():
    """Google Calendar API 서비스 객체를 반환합니다."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=creds)
    return service

def get_upcoming_events(service, calendar_id):
    """특정 캘린더에서 다가오는 이벤트를 가져옵니다."""
    now = datetime.datetime.utcnow().isoformat() + 'Z' # UTC 현재 시간
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=5, # 최대 5개의 이벤트만 가져옴
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events

def format_events_to_markdown(events):
    """가져온 이벤트를 마크다운 형식으로 변환합니다."""
    if not events:
        return "현재 예정된 일정이 없습니다. 🎉"

    markdown = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event.get('summary', '제목 없음')
        htmlLink = event.get('htmlLink', '#')

        # 날짜 형식 조정
        if 'dateTime' in event['start']:
            # 시간 정보가 있는 경우
            start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
            formatted_time = f"{start_dt.strftime('%m/%d %H:%M')} ~ {end_dt.strftime('%H:%M')}"
        else:
            # 종일 이벤트 (날짜만 있는 경우)
            start_dt = datetime.datetime.fromisoformat(start)
            formatted_time = start_dt.strftime('%Y/%m/%d (종일)')

        markdown.append(f"- **[{summary}]({htmlLink})** ({formatted_time})")
    return "\n".join(markdown)

def update_readme(markdown_content):
    """README.md 파일의 특정 섹션을 업데이트합니다."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()

    start_index = readme_content.find(START_DELIMITER)
    end_index = readme_content.find(END_DELIMITER)

    if start_index == -1 or end_index == -1:
        print(f"Error: Delimiters '{START_DELIMITER}' and/or '{END_DELIMITER}' not found in README.md")
        return

    before_content = readme_content[:start_index + len(START_DELIMITER)]
    after_content = readme_content[end_index:]

    new_readme_content = f"{before_content}\n{markdown_content}\n{after_content}"

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme_content)
    print("README.md updated successfully!")

if __name__ == "__main__":
    print("Starting Google Calendar README update script...")

    service = get_calendar_service()
    print("✅ Google Calendar service created")

    events = get_upcoming_events(service, CALENDAR_ID)
    print(f"📌 Events fetched: {events}")   # <-- 여기에 추가 (API 응답 확인)

    markdown_output = format_events_to_markdown(events)
    print("📄 Markdown Output:\n", markdown_output)  # <-- 여기에 추가 (형식 확인)

    update_readme(markdown_output)
    print("🚀 Finished updating README")
