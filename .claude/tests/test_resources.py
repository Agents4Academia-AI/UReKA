"""Tests for the resource-pull engine (`.claude/src/resources/`).

Pure-offline: credibility/registry logic is deterministic, and the Wikipedia
client is exercised by monkeypatching its network helpers with canned API JSON —
no live network, so these run anywhere.
"""

import sys
from pathlib import Path

import pytest

# Put `.claude/` on the path so `from src.resources...` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.resources import credibility, wikipedia  # noqa: E402
from src.resources.registries import tier_for  # noqa: E402


# --- registry tiers -----------------------------------------------------------

@pytest.mark.parametrize("host,expected", [
    ("en.wikipedia.org", "canonical"),
    ("fr.wikipedia.org", "canonical"),
    ("docs.python.org", "canonical"),
    ("distill.pub", "canonical"),
    ("lilianweng.github.io", "reputable"),
    ("huggingface.co", "reputable"),
    ("cs231n.stanford.edu", "reputable"),   # .edu suffix
    ("www.lilianweng.github.io", "reputable"),  # www stripped
    ("some-random-blog.example.com", "unknown"),
    ("", "unknown"),
])
def test_tier_for(host, expected):
    assert tier_for(host) == expected


# --- credibility scoring ------------------------------------------------------

def test_score_tiers_ordered():
    canon = credibility.score("https://en.wikipedia.org/wiki/X")["score"]
    rep = credibility.score("https://lilianweng.github.io/posts/x")["score"]
    unk = credibility.score("https://random.example.org/x")["score"]
    assert canon > rep > unk
    assert canon >= credibility.KEEP_THRESHOLD
    assert rep >= credibility.KEEP_THRESHOLD


def test_score_unknown_below_threshold_by_default():
    assert credibility.score("https://random.example.org/x")["score"] < credibility.KEEP_THRESHOLD


def test_https_penalty():
    https = credibility.score("https://random.example.org/x")["score"]
    http = credibility.score("http://random.example.org/x")["score"]
    assert http == pytest.approx(https - 0.10, abs=1e-6)


def test_signals_can_lift_unknown_over_threshold():
    r = credibility.score("https://expert.example.org/post",
                          has_references=True, author=True, year=2024, now_year=2026)
    assert r["score"] >= credibility.KEEP_THRESHOLD
    assert "references" in r["rationale"]


def test_blocked_domain_scores_zero(monkeypatch):
    monkeypatch.setattr("src.resources.credibility.tier_for", lambda h: "blocked")
    r = credibility.score("https://spam.example.com/x")
    assert r["score"] == 0.0 and r["tier"] == "blocked"


def test_score_clamped_to_unit_interval():
    r = credibility.score("https://en.wikipedia.org/wiki/X",
                          has_references=True, author=True, year=2025, now_year=2026)
    assert 0.0 <= r["score"] <= 1.0


# --- wikipedia client (network mocked) ----------------------------------------

def test_wikipedia_search_parses_hits(monkeypatch):
    canned = {"query": {"search": [
        {"title": "Diffusion model", "pageid": 1, "snippet": "a <span>class</span> of models"},
    ]}}
    monkeypatch.setattr(wikipedia, "_api", lambda params: canned)
    hits = wikipedia.search("diffusion", limit=3)
    assert hits[0]["title"] == "Diffusion model"
    assert hits[0]["snippet"] == "a class of models"          # html stripped
    assert hits[0]["url"].endswith("/wiki/Diffusion_model")    # spaces → underscores


def test_wikipedia_fetch_parses_page(monkeypatch):
    api_resp = {"query": {"pages": {"1": {
        "title": "Diffusion model", "fullurl": "https://en.wikipedia.org/wiki/Diffusion_model",
        "extract": "Body text\n\n== Training ==\nmore text",
    }}}}
    rest_resp = {"extract": "A one-paragraph summary.",
                 "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Diffusion_model"}},
                 "timestamp": "2026-01-01T00:00:00Z"}
    monkeypatch.setattr(wikipedia, "_api",
                        lambda params: api_resp if params.get("prop", "").startswith("extracts") else {"query": {"pages": {"1": {"extlinks": [{"*": "https://example.org"}]}}}})
    monkeypatch.setattr(wikipedia, "_get", lambda url: rest_resp)
    page = wikipedia.fetch("Diffusion model")
    assert page["title"] == "Diffusion model"
    assert page["summary"] == "A one-paragraph summary."
    assert "Training" in page["extract"]
    assert page["references"] == ["https://example.org"]


def test_wikipedia_fetch_missing_returns_none(monkeypatch):
    monkeypatch.setattr(wikipedia, "_api", lambda params: {"query": {"pages": {"-1": {"missing": ""}}}})
    assert wikipedia.fetch("Nonexistent Page ZZZ") is None


def test_wikipedia_network_failure_is_graceful(monkeypatch):
    monkeypatch.setattr(wikipedia, "_api", lambda params: None)
    assert wikipedia.search("x") == []
    assert wikipedia.fetch("x") is None
