def _create_post(client):
    response = client.post(
        "/api/v1/blog/posts",
        json={
            "title": "Practical interview preparation for software engineers",
            "content": (
                "A useful interview plan starts with role research, focused examples, "
                "and short practice sessions. This post explains a repeatable approach "
                "that candidates can adapt to different companies."
            ),
            "category": "Career",
            "tags": ["interview", "career"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["post"]


def test_blog_starts_without_seeded_fake_content(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.get("/api/v1/blog/posts")
    assert response.status_code == 200
    assert response.json() == {"posts": []}


def test_authenticated_user_can_publish_and_comment(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    post = _create_post(client)

    listing = client.get("/api/v1/blog/posts").json()["posts"]
    assert [item["id"] for item in listing] == [post["id"]]
    assert listing[0]["comments"] == []

    comment_response = client.post(
        f"/api/v1/blog/posts/{post['id']}/comments",
        json={"text": "The practice-session suggestion is concrete and helpful."},
    )
    assert comment_response.status_code == 201, comment_response.text
    detail = comment_response.json()["post"]
    assert len(detail["comments"]) == 1
    assert detail["comments"][0]["text"].startswith("The practice-session")

    reply_response = client.post(
        f"/api/v1/blog/posts/{post['id']}/comments",
        json={"text": "Glad that section helped.", "parent_id": int(detail["comments"][0]["id"])},
    )
    assert reply_response.status_code == 201
    assert len(reply_response.json()["post"]["comments"][0]["replies"]) == 1


def test_spam_content_is_rejected_before_database_write(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/v1/blog/posts",
        json={
            "title": "Guaranteed income from this opportunity",
            "content": "Guaranteed income is waiting. Visit https://a.test https://b.test https://c.test now.",
            "category": "Career",
            "tags": [],
        },
    )
    assert response.status_code == 422
    assert client.get("/api/v1/blog/posts").json() == {"posts": []}


def test_reactions_toggle_without_exposing_user_identities(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    post = _create_post(client)
    liked = client.post(
        "/api/v1/blog/reactions",
        json={"target_type": "post", "target_id": int(post["id"])},
    )
    assert liked.status_code == 200
    assert liked.json() == {"liked": True, "count": 1}

    detail = client.get(f"/api/v1/blog/posts/{post['slug']}").json()["post"]
    assert detail["likes"] == ["reaction-0"]
    assert "email" not in detail["author"]

    unliked = client.post(
        "/api/v1/blog/reactions",
        json={"target_type": "post", "target_id": int(post["id"])},
    )
    assert unliked.json() == {"liked": False, "count": 0}


def test_news_feed_returns_ten_latest_articles(client, monkeypatch):
    import httpx
    from routes import dashboard

    items = [
        {
            "id": index,
            "title": f"Current article {index}",
            "description": "A current technology article.",
            "url": f"https://dev.to/example/{index}",
            "social_image": f"https://images.example/{index}.jpg",
            "user": {"name": "DEV Author", "profile_image_90": "https://images.example/avatar.jpg"},
            "published_at": f"2026-07-{index + 1:02d}T10:00:00Z",
            "reading_time_minutes": 3,
            "tag_list": ["webdev"],
            "positive_reactions_count": index,
            "comments_count": 0,
        }
        for index in range(12)
    ]

    class FakeResponse:
        status_code = 200

        def json(self):
            return items

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    dashboard._blog_feed_cache = {"data": [], "ts": 0}
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    response = client.get("/api/v1/blog/feed")
    assert response.status_code == 200
    articles = response.json()["articles"]
    assert len(articles) == 10
    assert articles[0]["published_at"] > articles[-1]["published_at"]
