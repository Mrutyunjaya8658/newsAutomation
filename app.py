from nltk.corpus import stopwords as sw
from nltk.tokenize import word_tokenize as wt
from collections import Counter  
from dateutil import parser as date_parser
import feedparser
from flask import Flask, render_template, request, jsonify
from flask_paginate import Pagination, get_page_parameter
from datetime import datetime
import concurrent.futures

app = Flask(__name__)

NEWS_SOURCES = {
    'New York Times': 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'BBC News': 'http://feeds.bbci.co.uk/news/rss.xml',
    'CNN': 'http://rss.cnn.com/rss/edition.rss',
    'The Guardian': 'https://www.theguardian.com/world/rss',
    'Reuters': 'http://feeds.reuters.com/reuters/topNews',
    'Fox News': 'http://feeds.foxnews.com/foxnews/latest',
    'NBC News': 'https://feeds.nbcnews.com/nbcnews/top-stories',
    'ABC News': 'https://abcnews.go.com/abcnews/topstories',
    'CBS News': 'https://www.cbsnews.com/latest/rss/main',
    'USA Today': 'http://rssfeeds.usatoday.com/usatoday-NewsTopStories',
}

stop_words = set(sw.words('english'))

def extract_keywords(text):
    if not text:
        return []

    word_tokens = wt(text.lower())
    filtered_words = [word for word in word_tokens if word not in stop_words]

    word_counts = Counter(filtered_words)

    keywords = [word for word, count in word_counts.items() if not word.isdigit() and count > 1 and len(word) > 3]

    return keywords

def fetch_articles_from_url(url, page, per_page, category=None):
    feed = feedparser.parse(url)
    start = (page - 1) * per_page
    end = start + per_page
    articles = []
    for entry in feed.entries[start:end]:
        if category and 'category' in entry and category.lower() not in entry.category.lower():
            continue

        if 'published' in entry:
            published_date = date_parser.parse(entry.published)
        else:
            published_date = datetime.now()

        formatted_published_date = published_date.strftime('%A, %B %d, %Y, %I:%M %p')

        photo = None
        description = None
        
        if 'media_content' in entry and entry.media_content:
            photo = entry.media_content[0]['url']
        if 'summary' in entry and entry.summary:
            description = entry.summary

        title_keywords = extract_keywords(entry.title)
        description_keywords = extract_keywords(description) if description else []
        keywords = list(set(title_keywords + description_keywords))

        article = {
            'title': entry.title,
            'link': entry.link,
            'published': formatted_published_date,
            'photo': photo,
            'description': description,
            'keywords': keywords
        }
        articles.append(article)
    return articles

def fetch_news(feed_urls, page, per_page, category=None):
    articles = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_url = {executor.submit(fetch_articles_from_url, url, page, per_page, category): url for url in feed_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                articles.extend(future.result())
            except Exception as exc:
                print(f'Error fetching articles from {url}: {exc}')
    return articles

@app.route('/')
def index():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    category = request.args.get('category')
    ajax_request = request.args.get('ajax') == 'true' 

    all_articles = fetch_news(NEWS_SOURCES.values(), page, per_page, category)

    total_articles = sum(len(feedparser.parse(source).entries) for source in NEWS_SOURCES.values())
    pagination = Pagination(page=page, total=total_articles, per_page=per_page, css_framework='bootstrap4')

    if ajax_request:
        return jsonify(articles=all_articles, pagination=pagination.to_dict())
    else:
        return render_template('index.html', articles=all_articles, pagination=pagination)
    
if __name__ == '__main__':
    app.run(debug=True)