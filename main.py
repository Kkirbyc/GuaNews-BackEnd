from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
import anthropic
import json as json_lib
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://gua-news.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


@app.get("/")
def root():
    return {"message": "GuaNews API is running 🌍"}


@app.get("/news")
def get_news(category: str = "general", language: str = "en", q: str = None, pageSize: int = 12):
    url = "https://newsapi.org/v2/top-headlines"
    pageSize = max(1, min(pageSize, 50))
    params = {"apiKey": NEWS_API_KEY, "language": language, "pageSize": pageSize}
    if category != "general":
        params["category"] = category
    if q:
        params["q"] = q
    response = requests.get(url, params=params)
    data = response.json()
    if data.get("status") != "ok":
        return {"error": "Failed to fetch news", "details": data}
    articles = []
    for item in data.get("articles", []):
        if item.get("title") and item.get("description"):
            articles.append({
                "title": item.get("title"),
                "description": item.get("description"),
                "source": item.get("source", {}).get("name", "Unknown"),
                "url": item.get("url"),
                "publishedAt": item.get("publishedAt"),
                "urlToImage": item.get("urlToImage"),
            })
    return {"articles": articles, "total": len(articles)}


@app.get("/news/translated")
def get_news_translated(language: str = "zh", category: str = "general"):
    url = "https://newsapi.org/v2/top-headlines"
    params = {"apiKey": NEWS_API_KEY, "language": "en", "pageSize": 6}
    if category != "general":
        params["category"] = category
    response = requests.get(url, params=params)
    data = response.json()
    if data.get("status") != "ok":
        return {"error": "Failed to fetch news"}
    language_names = {"zh": "Simplified Chinese", "ja": "Japanese", "es": "Spanish", "fr": "French"}
    lang_name = language_names.get(language, "Simplified Chinese")
    articles = []
    for item in data.get("articles", []):
        if not item.get("title") or not item.get("description"):
            continue
        prompt = f"""Translate these two texts into {lang_name}.
Return ONLY a JSON object with keys "title" and "description", nothing else.

Title: {item.get("title")}
Description: {item.get("description")}"""
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            text = message.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            translated = json_lib.loads(text.strip())
        except:
            translated = {"title": item.get("title"), "description": item.get("description")}
        articles.append({
            "title": translated.get("title", item.get("title")),
            "description": translated.get("description", item.get("description")),
            "source": item.get("source", {}).get("name", "Unknown"),
            "url": item.get("url"),
            "publishedAt": item.get("publishedAt"),
        })
    return {"articles": articles, "language": language}


@app.get("/news/search")
def search_news(q: str, language: str = "en"):
    url = "https://newsapi.org/v2/everything"
    params = {"apiKey": NEWS_API_KEY, "q": q, "language": language, "pageSize": 10, "sortBy": "publishedAt"}
    response = requests.get(url, params=params)
    data = response.json()
    if data.get("status") != "ok":
        return {"error": "Search failed", "details": data}
    articles = []
    for item in data.get("articles", []):
        if item.get("title") and item.get("description"):
            articles.append({
                "title": item.get("title"),
                "description": item.get("description"),
                "source": item.get("source", {}).get("name", "Unknown"),
                "url": item.get("url"),
                "publishedAt": item.get("publishedAt"),
            })
    return {"articles": articles, "total": len(articles)}


@app.get("/summarize")
def summarize(title: str, description: str):
    prompt = f"""You are a news summarizer for GuaNews, a global news platform.
Summarize this news article into exactly 3 clear, concise bullet points.
Each point should be a complete sentence, easy for anyone to understand.
Be objective and factual.

Article title: {title}
Article description: {description}

Respond with exactly 3 bullet points, one per line, starting each with a number like "1.", "2.", "3."
Do not include any other text."""
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    summary_text = message.content[0].text
    points = [line.strip() for line in summary_text.strip().split("\n") if line.strip()]
    return {"points": points}


@app.get("/translate")
def translate(text: str, target_language: str = "zh"):
    language_names = {"zh": "Simplified Chinese", "ja": "Japanese", "es": "Spanish", "fr": "French", "de": "German", "ko": "Korean", "ar": "Arabic"}
    lang_name = language_names.get(target_language, target_language)
    prompt = f"""Translate the following news text into {lang_name}.
Keep the translation natural and professional.
Only return the translated text, nothing else.

Text to translate:
{text}"""
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return {"translated": message.content[0].text, "language": target_language}


@app.get("/illustration")
def generate_illustration(title: str):
    prompt = f"""You are an illustrator for GuaNews, a news app with a playful editorial style.
Based on this news headline, generate a simple SVG illustration in a cute hand-drawn sketch style.

News headline: "{title}"

Rules:
- SVG must be exactly 200x200 pixels: <svg width="200" height="200" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
- Draw 1-2 simple objects or characters directly related to the news topic
- Use only these colors: #1E5C3A (dark green) for main elements, #C8A96E (gold) for accents, #18181A (near black) for outlines
- Style: simple strokes, rounded lines, slightly wobbly/hand-drawn feel, cute and friendly
- Include a tiny detail that makes it charming (a small star, a smile, a little wave)
- Keep it minimal — 5 to 15 SVG elements maximum
- NO text, NO labels inside the SVG
- Only return the raw SVG code, nothing else, no explanation, no markdown backticks

Examples of what to draw:
- Trump / politics → small person at podium or handshake
- Climate / nature → leaf, tree, sun
- Finance / economy → coin stack, chart arrow going up
- Tech / AI → simple robot or circuit
- Sports → ball, trophy
- War / conflict → dove with olive branch (keep it peaceful)
- Health / medicine → heart, cross symbol
- Space → rocket, star, moon"""
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    svg_code = message.content[0].text.strip()
    if svg_code.startswith("```"):
        svg_code = svg_code.split("```")[1]
        if svg_code.startswith("svg"):
            svg_code = svg_code[3:]
    svg_code = svg_code.strip()
    return {"svg": svg_code, "title": title}
