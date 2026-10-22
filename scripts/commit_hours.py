"""커밋 시각을 시간대별로 집계해 README의 블록 막대를 갱신합니다.

GitHub GraphQL로 본인이 author인 커밋의 committedDate를 모아 한국 시간 기준으로
Morning / Daytime / Evening / Night 네 구간에 넣고, █/░ 문자로 막대를 그립니다.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

# --- 설정 ---
README_PATH = "README.md"
START_DELIMITER = "<!-- COMMIT_HOURS:START -->"
END_DELIMITER = "<!-- COMMIT_HOURS:END -->"
KST = timezone(timedelta(hours=9))
BAR_WIDTH = 25
REPO_PAGES = 3      # 30개씩 최대 3페이지 = 90개 저장소
# -------------

LABELS = [
    ("\U0001F31E", "Morning"),   # 06-12
    ("\U0001F306", "Daytime"),   # 12-18
    ("\U0001F303", "Evening"),   # 18-24
    ("\U0001F319", "Night"),     # 00-06
]

REPO_QUERY = """
query($login:String!, $id:ID!, $cursor:String) {
  user(login:$login) {
    repositories(first:30, ownerAffiliations:[OWNER], isFork:false,
                 orderBy:{field:PUSHED_AT, direction:DESC}, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first:100, author:{id:$id}) { nodes { committedDate } }
            }
          }
        }
      }
    }
  }
}
"""


def graphql(query, variables, token):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "commit-hours",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def collect_commit_dates(login, token):
    """본인이 author인 커밋의 committedDate 목록을 모읍니다."""
    user_id = graphql("query($l:String!){user(login:$l){id}}", {"l": login}, token)["user"]["id"]

    dates = []
    cursor = None
    for _ in range(REPO_PAGES):
        repositories = graphql(
            REPO_QUERY, {"login": login, "id": user_id, "cursor": cursor}, token
        )["user"]["repositories"]

        for repo in repositories["nodes"]:
            ref = repo.get("defaultBranchRef") or {}
            target = ref.get("target") or {}
            for commit in (target.get("history") or {}).get("nodes", []):
                dates.append(commit["committedDate"])

        if not repositories["pageInfo"]["hasNextPage"]:
            break
        cursor = repositories["pageInfo"]["endCursor"]

    return dates


def bucket_by_hour(dates):
    """한국 시간 기준으로 네 구간에 커밋을 나눕니다."""
    counts = [0, 0, 0, 0]
    for value in dates:
        moment = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        hour = moment.replace(tzinfo=timezone.utc).astimezone(KST).hour
        if 6 <= hour < 12:
            counts[0] += 1
        elif 12 <= hour < 18:
            counts[1] += 1
        elif 18 <= hour < 24:
            counts[2] += 1
        else:
            counts[3] += 1
    return counts


def render(counts):
    """블록 문자 막대 네 줄을 만듭니다."""
    total = sum(counts)
    if total == 0:
        return None

    lines = []
    for (emoji, name), count in zip(LABELS, counts):
        percent = count / total * 100
        filled = round(percent / 100 * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        lines.append(
            "{} {:<9}{:>5} commits   {}   {:>5.1f}%".format(emoji, name, count, bar, percent)
        )

    # 가장 커밋이 많은 구간을 제목으로 (productive-box와 같은 방식)
    headline = LABELS[counts.index(max(counts))]
    title = "I'm a {} {}".format(headline[1].lower(), headline[0])

    return "**{}**\n\n```text\n{}\n```".format(title, "\n".join(lines))


def update_readme(block):
    with open(README_PATH, "r", encoding="utf-8") as handle:
        content = handle.read()

    start = content.find(START_DELIMITER)
    end = content.find(END_DELIMITER)
    if start == -1 or end == -1:
        print("Error: delimiters not found in README.md")
        return False

    before = content[:start]
    after = content[end + len(END_DELIMITER):]

    # 구분자도 다시 써 줘야 다음 실행에서 섹션을 찾을 수 있습니다.
    updated = "{}{}\n{}\n{}{}".format(
        before, START_DELIMITER, block, END_DELIMITER, after
    )

    with open(README_PATH, "w", encoding="utf-8") as handle:
        handle.write(updated)

    print("README.md updated successfully!")
    return True


if __name__ == "__main__":
    token = os.environ.get("GH_TOKEN")
    login = os.environ.get("LOGIN")
    if not token or not login:
        raise SystemExit("GH_TOKEN / LOGIN 환경 변수가 필요합니다")

    commit_dates = collect_commit_dates(login, token)
    print("Collected {} commits".format(len(commit_dates)))

    counts = bucket_by_hour(commit_dates)
    print("Morning/Daytime/Evening/Night = {}".format(counts))

    block = render(counts)
    if block is None:
        print("::warning::커밋이 하나도 없어 README를 건드리지 않습니다")
        raise SystemExit(0)

    update_readme(block)
