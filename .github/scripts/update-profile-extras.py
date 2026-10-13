"""Refresh public profile modules without third-party card endpoints."""

import argparse
from datetime import datetime, timezone, timedelta
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
import urllib.request

OWNER = "qilinbro"
SITE = "https://qilinbro.github.io/"
LOCAL_TIME = timezone(timedelta(hours=8))
SVG_NS = "http://www.w3.org/2000/svg"
COLORS = {"TypeScript": "#3178c6", "Python": "#d9aa37", "JavaScript": "#c7a416",
          "HTML": "#e34c26", "CSS": "#8b64bf", "Markdown": "#6296bd",
          "JSON": "#679c50", "YAML": "#bf6384", "Other": "#6b8594",
          "SSH Config": "#7d9873"}


def fetch(url):
    headers = {"User-Agent": "qilinbro-profile-upgrade"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
        headers["Accept"] = "application/vnd.github+json"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return response.read().decode("utf-8")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def md(value):
    value = re.sub(r"[\r\n\t]+", " ", str(value or ""))
    return re.sub(r"([\\`*_|\[\]])", r"\\\1", escape(value))


def repo_url(name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
        raise ValueError("Invalid public repository name")
    return "https://github.com/" + name


def section(document, name, content):
    pattern = rf"(<!--START_SECTION:{name}-->).*?(<!--END_SECTION:{name}-->)"
    result, count = re.subn(pattern, lambda m: m[1] + "\n\n" + content.strip() + "\n\n" + m[2], document, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one {name} section")
    return result


class NotesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_heading = False
        self.link = None
        self.title = []
        self.notes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h3":
            self.in_heading = True
        if tag == "a" and self.in_heading and re.fullmatch(r"posts/[A-Za-z0-9-]+\.html", attrs.get("href", "")):
            self.link = SITE + attrs["href"]
            self.title = []

    def handle_data(self, data):
        if self.link:
            self.title.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.link:
            self.notes.append(("".join(self.title).strip(), self.link))
            self.link = None
        if tag == "h3":
            self.in_heading = False


def catalog(repos):
    result = []
    for label, fork in (("自主仓库", False), ("Fork 与开源探索", True)):
        result.append(f"**{label}**\n")
        for repo in repos:
            if bool(repo.get("fork")) != fork:
                continue
            name = repo["name"]
            language = md(repo.get("language") or "Mixed / Notes")
            description = re.sub(r"\s+", " ", repo.get("description") or "").strip()
            detail = " — " + md(description[:90] + ("…" if len(description) > 90 else "")) if description else ""
            archived = " · Archived" if repo.get("archived") else ""
            result.append(f"- [{md(name)}]({repo_url(OWNER + '/' + name)}) · {language}{archived}{detail}")
        result.append("")
    return "\n".join(result)


def activity(events):
    names = {"PushEvent": "更新代码", "CreateEvent": "创建", "PullRequestEvent": "Pull request",
             "IssuesEvent": "Issue", "IssueCommentEvent": "参与讨论", "ReleaseEvent": "发布版本",
             "WatchEvent": "关注项目", "ForkEvent": "Fork 项目", "PullRequestReviewEvent": "代码审阅"}
    result, seen = [], set()
    for event in sorted(events, key=lambda e: e.get("created_at", ""), reverse=True):
        name = event.get("repo", {}).get("name", "")
        kind = event.get("type")
        if name == OWNER + "/" + OWNER or kind not in names or event.get("public") is False:
            continue
        when = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).astimezone(LOCAL_TIME).strftime("%Y-%m-%d")
        key = (when, name, kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(f"- `{when}` · {names[kind]} · [{md(name)}]({repo_url(name)})")
        if len(result) == 6:
            break
    return "\n".join(result) or "公开活动暂未返回，欢迎查看 [GitHub 活动记录](https://github.com/qilinbro?tab=overview)。"


def palette(dark):
    return {"bg": "#0d1117" if dark else "#f6f8fa", "ink": "#c9d1d9" if dark else "#1f2937",
            "muted": "#8b949e" if dark else "#576574", "line": "#30363d" if dark else "#d8dee4",
            "accent": "#58c9b9" if dark else "#0f766e", "track": "#212b36" if dark else "#e4eaf0"}


def svg_start(title, desc, height, p):
    return [f'<svg xmlns="{SVG_NS}" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>',
            f'<rect x="1" y="1" width="1198" height="{height-2}" rx="16" fill="{p["bg"]}" stroke="{p["line"]}"/>',
            '<g font-family="system-ui,-apple-system,Segoe UI,sans-serif">']


def text(x, y, value, color, size=22, weight=400):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'


def overview(repos, dark):
    p = palette(dark)
    owned = [r for r in repos if not r.get("fork")]
    languages = {r["language"] for r in owned if r.get("language")}
    metrics = ((len(repos), "公开仓库 / Public repos"), (len(owned), "自主仓库 / Original repos"),
               (sum(r.get("stargazers_count", 0) for r in owned), "自主仓库获得的 Stars"), (len(languages), "自主项目主要语言"))
    parts = svg_start("Public workbench", "GitHub public repository overview, excluding private data", 186, p)
    parts.append(text(32, 35, "PUBLIC WORKBENCH  /  公开创作面板", p["muted"], 16, 600))
    for index, (number, label) in enumerate(metrics):
        x = 32 + 298 * index
        if index:
            parts.append(f'<path d="M{x-22} 60V156" stroke="{p["line"]}"/>')
        parts.extend((text(x, 115, number, p["accent"], 48, 700), text(x, 151, label, p["ink"], 19)))
    return "\n".join(parts + ["</g></svg>"])


def coding(document, dark):
    block = re.search(r"<!--START_SECTION:waka-->(.*?)<!--END_SECTION:waka-->", document, re.S)
    if not block:
        raise ValueError("Missing WakaTime data")
    total = re.search(r"Total Time:\s*(.+)", block[1])
    period = re.search(r"From:\s*(.+)", block[1])
    rows = []
    for line in block[1].splitlines():
        match = re.match(r"^(.+?)\s{2,}(.+?)\s{2,}.+?\s+(\d+(?:\.\d+)?)\s*%\s*$", line)
        if match:
            rows.append((match[1].strip(), match[2].strip(), float(match[3])))
    if not total or not period or not rows:
        raise ValueError("Invalid WakaTime content; keep the previous chart")
    p = palette(dark)
    parts = svg_start("Coding time / 编程时间", "WakaTime all-time data: " + total[1].strip(), 434, p)
    parts.extend((text(32, 39, "CODING TIME  /  编程时间", p["muted"], 16, 600),
                  text(32, 88, total[1].strip(), p["ink"], 38, 700),
                  text(32, 120, period[1].strip(), p["muted"], 17)))
    cursor = 32
    for language, duration, percent in rows:
        width = min(percent, max(0, (1168-cursor)/11.36)) * 11.36
        parts.append(f'<rect x="{cursor:.2f}" y="146" width="{width:.2f}" height="14" fill="{COLORS.get(language,p["accent"])}"/>')
        cursor += width
    for index, (language, duration, percent) in enumerate(rows[:10]):
        x, y = 32 + (index // 5) * 596, 200 + (index % 5) * 44
        color = COLORS.get(language, p["accent"])
        parts.extend((f'<circle cx="{x+5}" cy="{y-6}" r="5" fill="{color}"/>', text(x+21, y, language, p["ink"], 19, 600),
                      text(x+204, y, duration, p["muted"], 16), text(x+457, y, f"{percent:.2f}%", p["ink"], 17),
                      f'<rect x="{x+21}" y="{y+10}" width="496" height="4" rx="2" fill="{p["track"]}"/>',
                      f'<rect x="{x+21}" y="{y+10}" width="{496*percent/100:.2f}" height="4" rx="2" fill="{color}"/>'))
    parts.append(text(32, 416, "WakaTime · All time · 原始明细见下方折叠面板", p["muted"], 15))
    return "\n".join(parts + ["</g></svg>"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos-file", type=Path)
    parser.add_argument("--events-file", type=Path)
    parser.add_argument("--blog-file", type=Path)
    args = parser.parse_args()
    if args.repos_file:
        repos = json.loads(args.repos_file.read_text(encoding="utf-8"))
    else:
        repos = []
        for page in range(1, 11):
            batch = json.loads(fetch(f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner&sort=updated&page={page}"))
            repos.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError("Public repository pagination limit reached")
    repos = sorted((r for r in repos if not r.get("private")), key=lambda r: r.get("pushed_at") or r.get("updated_at", ""), reverse=True)
    events = json.loads(args.events_file.read_text(encoding="utf-8") if args.events_file else fetch(f"https://api.github.com/users/{OWNER}/events/public?per_page=50"))
    notes = NotesParser()
    notes.feed(args.blog_file.read_text(encoding="utf-8") if args.blog_file else fetch("https://raw.githubusercontent.com/qilinbro/qilinbro.github.io/main/blog.html"))
    if not notes.notes:
        raise ValueError("No public notes returned; keep existing notes")
    readme_path = Path("README.md")
    original = readme_path.read_text(encoding="utf-8")
    updated = section(original, "catalog", catalog(repos))
    updated = section(updated, "activity", activity(events))
    updated = section(updated, "notes", "\n".join(f"- [{md(title)}]({url})" for title, url in notes.notes[:7]))
    weekly_index = Path("weekly/README.md").read_text(encoding="utf-8")
    issues = re.findall(r"\[([^\]]+)\]\((\d{4}/issue-(\d+)\.md)\)", weekly_index)
    issues = [issue for issue in issues if (Path("weekly") / issue[1]).is_file()]
    if not issues:
        raise ValueError("No published weekly issue found")
    title, relative_path, _ = max(issues, key=lambda issue: (int(issue[1][:4]), int(issue[2])))
    updated = section(updated, "weekly", f"[最新一期：{md(title)}](weekly/{relative_path}) · [全部微刊](weekly/README.md)")
    outputs = {"overview-light.svg": overview(repos, False), "overview-dark.svg": overview(repos, True),
               "coding-light.svg": coding(original, False), "coding-dark.svg": coding(original, True)}
    profile = Path("profile")
    profile.mkdir(exist_ok=True)
    for filename, content in outputs.items():
        (profile / filename).write_text(content + "\n", encoding="utf-8", newline="\n")
    readme_path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated public profile modules: {len(repos)} repositories, {len(notes.notes)} notes, four SVGs.")


if __name__ == "__main__":
    main()
