from app.service.clients.github_client import GitHubClient
from app.service.clients.huggingface_client import HuggingFaceClient
from app.service.clients.linkedin_client import LinkedInClient


class TestGitHubExtraction:
    def test_extract_basic(self):
        raw = {
            "user": {
                "login": "octocat",
                "name": "The Octocat",
                "bio": "A friendly cat",
                "avatar_url": "https://example.com/avatar.jpg",
                "company": "GitHub",
                "location": "San Francisco",
                "blog": "https://octocat.dev",
                "public_repos": 10,
                "followers": 500,
            },
            "repos": [
                {
                    "fork": False,
                    "stargazers_count": 100,
                    "language": "Python",
                    "topics": ["fastapi", "backend"],
                },
                {
                    "fork": False,
                    "stargazers_count": 50,
                    "language": "Rust",
                    "topics": ["cli"],
                },
                {
                    "fork": True,
                    "stargazers_count": 1000,
                    "language": "JavaScript",
                    "topics": [],
                },
            ],
        }
        result = GitHubClient.extract(raw)
        assert result["display_name"] == "The Octocat"
        assert result["bio"] == "A friendly cat"
        assert result["total_stars"] == 150  # excludes fork
        assert result["total_followers"] == 500
        assert result["total_repos"] == 10
        assert "Python" in result["languages"]
        assert "Rust" in result["languages"]
        assert "JavaScript" not in result["languages"]  # fork excluded
        assert "fastapi" in result["topics"]
        assert result["total_contributions"] == 2  # non-fork repos

    def test_extract_empty(self):
        raw = {"user": {}, "repos": []}
        result = GitHubClient.extract(raw)
        assert result["display_name"] == ""
        assert result["total_stars"] == 0
        assert result["languages"] == []


class TestLinkedInExtraction:
    def test_extract_basic(self):
        raw = {
            "full_name": "Jane Doe",
            "headline": "Senior Engineer at BigCo",
            "summary": "I build things",
            "city": "New York",
            "country_full_name": "United States",
            "profile_pic_url": "https://example.com/pic.jpg",
            "experiences": [
                {
                    "company": "BigCo",
                    "title": "Senior Engineer",
                    "starts_at": {"year": 2020, "month": 3},
                    "ends_at": None,
                },
                {
                    "company": "SmallCo",
                    "title": "Junior Dev",
                    "starts_at": {"year": 2017, "month": 1},
                    "ends_at": {"year": 2020, "month": 2},
                },
            ],
            "skills": ["Python", "Machine Learning", "FastAPI"],
        }
        result = LinkedInClient.extract(raw)
        assert result["display_name"] == "Jane Doe"
        assert result["headline"] == "Senior Engineer at BigCo"
        assert result["current_title"] == "Senior Engineer"
        assert result["current_company"] == "BigCo"
        assert len(result["job_history"]) == 2
        assert "Python" in result["skills"]
        assert result["years_of_experience"] is not None
        assert result["years_of_experience"] >= 7

    def test_extract_empty(self):
        raw = {}
        result = LinkedInClient.extract(raw)
        assert result["display_name"] is None
        assert result["job_history"] == []
        assert result["skills"] == []


class TestHuggingFaceExtraction:
    def test_extract_basic(self):
        raw = {
            "user": {
                "fullname": "ML Researcher",
                "user": "researcher",
                "avatarUrl": "https://hf.co/avatar.jpg",
            },
            "models": [
                {"downloads": 1000, "paperswithcode_id": "abc"},
                {"downloads": 500, "paperswithcode_id": None},
            ],
            "datasets": [{"id": "ds1"}],
            "spaces": [{"id": "sp1"}, {"id": "sp2"}],
        }
        result = HuggingFaceClient.extract(raw)
        assert result["display_name"] == "ML Researcher"
        assert result["total_hf_models"] == 2
        assert result["total_hf_datasets"] == 1
        assert result["total_hf_spaces"] == 2
        assert result["total_hf_downloads"] == 1500
        assert result["total_papers"] == 1

    def test_extract_empty(self):
        raw = {"user": {}, "models": [], "datasets": [], "spaces": []}
        result = HuggingFaceClient.extract(raw)
        assert result["display_name"] == ""
        assert result["total_hf_models"] == 0
        assert result["total_hf_downloads"] == 0
