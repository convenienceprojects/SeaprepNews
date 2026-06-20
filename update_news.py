import json, re, sys, html, datetime, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

SOURCES = [
    {"name": "The Seattle Prep Panther", "type": "panther",
     "rss": "https://seapreppanther.org/feed/rss/", "icon": "📰"},
]

MAX_STORIES = 25
OUTPUT_JSON = "news.json"
TIMEOUT = 30

CATEGORY_MAP = {
    "prep life": "Prep Life", "opinion": "Opinion", "sports": "Athletics",
    "feature": "Features", "entertainment": "Entertainment", "humor": "Humor",
    "news": "News",
}

def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def categorize(raw_cat):
    return CATEGORY_MAP.get((raw_cat or "").lower().strip(), "News")

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PrepNewsBot)"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except Exception as e:
        print(f"  ! could not fetch {url}: {e}", file=sys.stderr)
        return None

def parse_date(pub):
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            dt = datetime.datetime.strptime(pub, fmt)
            return dt.isoformat(), dt.strftime("%b %-d, %Y")
        except ValueError:
            continue
    return "1970-01-01T00:00:00", (pub or "Recent")

def parse_rss(xml_bytes, source):
    stories = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ! XML parse error for {source['name']}: {e}", file=sys.stderr)
        return stories
    ns = {"dc": "http://purl.org/dc/elements/1.1/",
          "content": "http://purl.org/rss/1.0/modules/content/"}
    for item in root.iter("item"):
        title = clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        desc = clean(item.findtext("description"))
        author = clean(item.findtext("dc:creator", namespaces=ns)) or source["name"]
        raw_cat = item.findtext("category") or ""
        pub = (item.findtext("pubDate") or "").strip()
        iso, label = parse_date(pub)
        if not title or not link:
            continue
        stories.append({
            "headline": title, "body": desc, "byline": author,
            "category": categorize(raw_cat), "source": source["name"],
            "sourceType": source["type"], "sourceIcon": source["icon"],
            "link": link, "date_iso": iso, "date": label,
        })
    return stories

def build():
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] Starting news update")
    all_stories = []
    local = None
    if "--local" in sys.argv:
        local = sys.argv[sys.argv.index("--local") + 1]
    for src in SOURCES:
        print(f"  - {src['name']}")
        data = Path(local).read_bytes() if local else fetch(src["rss"])
        if not data:
            continue
        got = parse_rss(data, src)
        print(f"      -> {len(got)} stories")
        all_stories.extend(got)
    seen, unique = set(), []
    for s in sorted(all_stories, key=lambda x: x["date_iso"], reverse=True):
        if s["link"] in seen:
            continue
        seen.add(s["link"])
        unique.append(s)
    unique = unique[:MAX_STORIES]
    payload = {
        "updated": datetime.datetime.now().isoformat(),
        "updated_label": datetime.datetime.now().strftime("%B %-d, %Y at %-I:%M %p"),
        "count": len(unique),
        "stories": unique,
    }
    Path(OUTPUT_JSON).write_text(json.dumps(payload, indent=2))
    print(f"  wrote {len(unique)} stories to {OUTPUT_JSON}")
    return payload

if __name__ == "__main__":
    build()
