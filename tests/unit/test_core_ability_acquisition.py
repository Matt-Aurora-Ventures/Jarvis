"""
Unit tests for core/ability_acquisition.py.

Tests:
- AbilityAcquisition class initialization
- Directory and database management
- Ability discovery from web/ollama sources
- Ability evaluation with mocked AI
- Acquisition workflows (Ollama, GitHub, HuggingFace, Research)
- Integration of acquired abilities
- Full acquisition cycle
- Status reporting
- Global singleton management

All external dependencies are mocked:
- providers.generate_text (AI text generation)
- research_engine.get_research_engine (web search)
- subprocess calls (Ollama CLI)
- requests (HTTP calls)
- evolution module (improvement application)
- guardian module (safety validation)
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call
from typing import Dict, Any


# --- Fixtures ---


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directories for testing."""
    abilities_path = tmp_path / "data" / "abilities"
    models_path = tmp_path / "data" / "models"
    abilities_path.mkdir(parents=True, exist_ok=True)
    models_path.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for AbilityAcquisition."""
    with patch("core.ability_acquisition.ABILITIES_PATH") as mock_abilities_path, \
         patch("core.ability_acquisition.MODELS_PATH") as mock_models_path, \
         patch("core.ability_acquisition.ACQUISITION_LOG_PATH") as mock_log_path:
        yield {
            "abilities_path": mock_abilities_path,
            "models_path": mock_models_path,
            "log_path": mock_log_path,
        }


@pytest.fixture
def mock_research_engine():
    """Mock the research engine for web searches."""
    mock_engine = MagicMock()
    mock_engine.search_web.return_value = [
        {
            "title": "Test Model - Open Source LLM",
            "url": "https://github.com/test/model",
            "snippet": "A free open source language model for testing",
        },
        {
            "title": "Free AI Tool for Automation",
            "url": "https://huggingface.co/test/model",
            "snippet": "Free automation tool with AI capabilities",
        },
    ]
    return mock_engine


@pytest.fixture
def sample_discovery():
    """Sample discovery object for testing."""
    return {
        "source": "web_search",
        "title": "Test Open Source Model",
        "url": "https://github.com/test/model",
        "snippet": "A free open source language model with reasoning capabilities",
        "query": "free crypto trading AI models",
    }


@pytest.fixture
def sample_ollama_discovery():
    """Sample Ollama model discovery."""
    return {
        "source": "ollama",
        "title": "qwen2.5:3b",
        "size": "2.0GB",
        "modified": "2026-01-01T00:00:00Z",
        "digest": "abc123def456...",
    }


@pytest.fixture
def sample_ability():
    """Sample acquired ability for testing."""
    return {
        "id": "ollama_12345",
        "type": "ollama_model",
        "name": "qwen2.5:3b",
        "source": "ollama",
        "acquired_at": datetime.now().isoformat(),
        "capabilities": ["text_generation", "conversation"],
        "size": "2.0GB",
    }


@pytest.fixture
def acquisition_instance(tmp_path):
    """Create an AbilityAcquisition instance with temp directories."""
    abilities_path = tmp_path / "data" / "abilities"
    models_path = tmp_path / "data" / "models"
    log_path = tmp_path / "data" / "ability_acquisitions.log"

    abilities_path.mkdir(parents=True, exist_ok=True)
    models_path.mkdir(parents=True, exist_ok=True)

    with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
         patch("core.ability_acquisition.MODELS_PATH", models_path), \
         patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
         patch("core.ability_acquisition.research_engine"), \
         patch("core.ability_acquisition.providers"), \
         patch("core.ability_acquisition.evolution"), \
         patch("core.ability_acquisition.guardian"):
        from core.ability_acquisition import AbilityAcquisition
        instance = AbilityAcquisition()
        # Store paths for test verification
        instance._test_abilities_path = abilities_path
        instance._test_models_path = models_path
        instance._test_log_path = log_path
        yield instance


# --- Test Classes ---


class TestAbilityAcquisitionInit:
    """Test AbilityAcquisition initialization."""

    def test_init_creates_directories(self, tmp_path):
        """Test that initialization creates required directories."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            assert abilities_path.exists()
            assert models_path.exists()

    def test_init_loads_empty_abilities_database(self, tmp_path):
        """Test initialization with no existing database."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            assert "acquired" in instance.abilities
            assert "pending" in instance.abilities
            assert "failed" in instance.abilities
            assert "categories" in instance.abilities
            assert len(instance.abilities["acquired"]) == 0

    def test_init_loads_existing_abilities_database(self, tmp_path):
        """Test initialization loads existing database."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        # Create existing database
        existing_abilities = {
            "acquired": [{"id": "test_1", "name": "TestAbility"}],
            "pending": [],
            "failed": [],
            "categories": {
                "reasoning": [],
                "coding": [],
                "conversation": [],
                "analysis": [],
                "automation": [],
            },
        }
        with open(abilities_path / "abilities.json", "w") as f:
            json.dump(existing_abilities, f)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            assert len(instance.abilities["acquired"]) == 1
            assert instance.abilities["acquired"][0]["id"] == "test_1"

    def test_init_loads_existing_models_database(self, tmp_path):
        """Test initialization loads existing models database."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        # Create existing models database
        existing_models = {
            "available": ["model1", "model2"],
            "installed": ["model1"],
            "tested": [],
        }
        with open(models_path / "models.json", "w") as f:
            json.dump(existing_models, f)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            assert "model1" in instance.models["installed"]
            assert len(instance.models["available"]) == 2

    def test_init_default_categories(self, acquisition_instance):
        """Test that default categories are initialized."""
        expected_categories = ["reasoning", "coding", "conversation", "analysis", "automation"]
        for cat in expected_categories:
            assert cat in acquisition_instance.abilities["categories"]


class TestSaveAbilities:
    """Test _save_abilities method."""

    def test_save_abilities_writes_json(self, acquisition_instance):
        """Test that abilities are saved to JSON file."""
        acquisition_instance.abilities["acquired"].append({
            "id": "test_save_1",
            "name": "SaveTestAbility",
        })
        acquisition_instance._save_abilities()

        abilities_file = acquisition_instance._test_abilities_path / "abilities.json"
        assert abilities_file.exists()

        with open(abilities_file) as f:
            saved = json.load(f)
        assert len(saved["acquired"]) == 1
        assert saved["acquired"][0]["id"] == "test_save_1"

    def test_save_models_writes_json(self, acquisition_instance):
        """Test that models database is saved to JSON file."""
        acquisition_instance.models["installed"].append("test-model")
        acquisition_instance._save_abilities()

        models_file = acquisition_instance._test_models_path / "models.json"
        assert models_file.exists()

        with open(models_file) as f:
            saved = json.load(f)
        assert "test-model" in saved["installed"]


class TestLogAcquisition:
    """Test _log_acquisition method."""

    def test_log_acquisition_creates_entry(self, acquisition_instance):
        """Test that acquisition logging creates log entries."""
        acquisition_instance._log_acquisition("test_action", {"key": "value"})

        log_file = acquisition_instance._test_log_path
        assert log_file.exists()

        with open(log_file) as f:
            line = f.readline()
            entry = json.loads(line)

        assert entry["action"] == "test_action"
        assert entry["details"]["key"] == "value"
        assert "timestamp" in entry

    def test_log_acquisition_appends(self, acquisition_instance):
        """Test that logging appends to existing file."""
        acquisition_instance._log_acquisition("action1", {"data": 1})
        acquisition_instance._log_acquisition("action2", {"data": 2})

        log_file = acquisition_instance._test_log_path
        with open(log_file) as f:
            lines = f.readlines()

        assert len(lines) == 2


class TestDiscoverOpenSourceModels:
    """Test discover_open_source_models method."""

    def test_discover_searches_multiple_queries(self, tmp_path):
        """Test that discovery searches with multiple queries."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = []

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            discoveries = instance.discover_open_source_models()

            # Should call search_web multiple times
            assert mock_engine.search_web.call_count > 0

    def test_discover_filters_by_keywords(self, tmp_path):
        """Test that discoveries are filtered by relevant keywords."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Open Source Model Test", "url": "http://test.com", "snippet": "test"},
            {"title": "Unrelated Blog Post", "url": "http://blog.com", "snippet": "random"},
        ]

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            discoveries = instance.discover_open_source_models()

            # Only "Open Source Model" should be included due to keyword filter
            model_titles = [d.get("title", "") for d in discoveries]
            assert any("Open Source" in t or "Model" in t for t in model_titles)

    def test_discover_ollama_models_success(self, tmp_path):
        """Test successful Ollama model discovery."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = []

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:8b", "size": "4.7GB", "modified": "2026-01-01"},
                {"name": "qwen2.5:3b", "size": "2.0GB", "modified": "2026-01-01"},
            ]
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.return_value = mock_response

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            discoveries = instance.discover_open_source_models()

            ollama_discoveries = [d for d in discoveries if d.get("source") == "ollama"]
            assert len(ollama_discoveries) == 2
            assert ollama_discoveries[0]["title"] == "llama3:8b"

    def test_discover_ollama_models_error(self, tmp_path):
        """Test Ollama discovery handles network errors."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = []

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.side_effect = Exception("Connection refused")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            # Should not raise, just log error
            discoveries = instance.discover_open_source_models()
            assert isinstance(discoveries, list)


class TestEvaluateAbility:
    """Test evaluate_ability method."""

    def test_evaluate_returns_high_rating(self, tmp_path, sample_discovery):
        """Test evaluation returns high rating for relevant abilities."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.return_value = "Rating: 8 - This model is excellent for crypto trading and autonomy."

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            assert result["rating"] == 8
            assert result["recommended"] is True
            assert "reasoning" in result

    def test_evaluate_returns_low_rating(self, tmp_path, sample_discovery):
        """Test evaluation returns low rating for irrelevant abilities."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.return_value = "Rating: 3 - This model is not relevant to our goals."

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            assert result["rating"] == 3
            assert result["recommended"] is False

    def test_evaluate_handles_api_error(self, tmp_path, sample_discovery):
        """Test evaluation handles API errors gracefully."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.side_effect = Exception("API Error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            # Should return default values on error
            assert result["rating"] == 5
            assert result["recommended"] is False

    def test_evaluate_handles_empty_response(self, tmp_path, sample_discovery):
        """Test evaluation handles empty API response."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.return_value = None

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            assert result["rating"] == 5
            assert result["recommended"] is False

    def test_evaluate_extracts_rating_from_text(self, tmp_path, sample_discovery):
        """Test rating extraction from various text formats."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.return_value = "I would give this a 9 out of 10."

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            assert result["rating"] == 9


class TestAcquireAbility:
    """Test acquire_ability method."""

    def test_acquire_skips_already_acquired(self, tmp_path, sample_discovery):
        """Test that already acquired abilities are skipped."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Pre-add the ability
            ability_id = f"{sample_discovery.get('source', 'unknown')}_{hash(sample_discovery.get('title', ''))}"
            instance.abilities["acquired"].append({"id": ability_id})

            result = instance.acquire_ability(sample_discovery)
            assert result is False

    def test_acquire_github_project(self, tmp_path):
        """Test GitHub project acquisition."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Test GitHub Project",
            "url": "https://github.com/test/project",
            "snippet": "A test project",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)

            assert result is True
            assert len(instance.abilities["acquired"]) == 1
            assert instance.abilities["acquired"][0]["type"] == "github_project"

    def test_acquire_huggingface_model(self, tmp_path):
        """Test HuggingFace model acquisition."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Test HuggingFace Model",
            "url": "https://huggingface.co/test/model",
            "snippet": "A test HuggingFace model",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)

            assert result is True
            assert len(instance.abilities["acquired"]) == 1
            assert instance.abilities["acquired"][0]["type"] == "huggingface_model"

    def test_acquire_researched_ability(self, tmp_path):
        """Test researched ability acquisition with capability detection."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "AI Reasoning Tool",
            "url": "https://example.com/tool",
            "snippet": "A tool for reasoning and logic analysis with code programming capabilities",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)

            assert result is True
            acquired = instance.abilities["acquired"][0]
            assert acquired["type"] == "researched_ability"
            assert "reasoning" in acquired["capabilities"]
            assert "coding" in acquired["capabilities"]
            assert "analysis" in acquired["capabilities"]

    def test_acquire_handles_exception(self, tmp_path):
        """Test acquire_ability handles exceptions gracefully."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "ollama",
            "title": "test-model",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            mock_subprocess.run.side_effect = Exception("Unexpected error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)
            assert result is False


class TestAcquireOllamaModel:
    """Test _acquire_ollama_model method."""

    def test_acquire_ollama_checks_ollama_availability(self, tmp_path, sample_ollama_discovery):
        """Test Ollama acquisition checks if Ollama CLI is available."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            # Simulate Ollama not installed
            mock_subprocess.run.return_value = MagicMock(returncode=1)

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(sample_ollama_discovery, "test_id")
            assert result is False

    def test_acquire_ollama_success(self, tmp_path, sample_ollama_discovery):
        """Test successful Ollama model acquisition."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            # Simulate successful Ollama commands
            mock_subprocess.run.return_value = MagicMock(returncode=0, stderr="")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(sample_ollama_discovery, "test_id")

            assert result is True
            assert len(instance.abilities["acquired"]) == 1
            assert "qwen2.5:3b" in instance.models["installed"]

    def test_acquire_ollama_pull_failure(self, tmp_path, sample_ollama_discovery):
        """Test Ollama model pull failure handling."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            # First call succeeds (version check), second fails (pull)
            mock_subprocess.run.side_effect = [
                MagicMock(returncode=0),  # version check
                MagicMock(returncode=1, stderr="Pull failed"),  # pull
            ]

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(sample_ollama_discovery, "test_id")
            assert result is False

    def test_acquire_ollama_empty_model_name(self, tmp_path):
        """Test Ollama acquisition with empty model name."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {"source": "ollama", "title": ""}

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(discovery, "test_id")
            assert result is False


class TestIntegrateAbility:
    """Test integrate_ability method."""

    def test_integrate_ollama_model(self, tmp_path, sample_ability):
        """Test integrating an Ollama model."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.integrate_ability(sample_ability)
            assert result is True

    def test_integrate_researched_ability_safe(self, tmp_path):
        """Test integrating a safe researched ability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        ability = {
            "id": "research_123",
            "type": "researched_ability",
            "name": "Test Ability",
            "source": "research",
            "capabilities": ["reasoning"],
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution") as mock_evolution, \
             patch("core.ability_acquisition.guardian") as mock_guardian:
            mock_guardian.validate_code_for_safety.return_value = (True, "Safe")
            mock_evolution.apply_improvement.return_value = {"status": "applied"}

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.integrate_ability(ability)
            assert result is True

    def test_integrate_researched_ability_unsafe(self, tmp_path):
        """Test that unsafe researched abilities are not integrated."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        ability = {
            "id": "research_unsafe",
            "type": "researched_ability",
            "name": "Unsafe Ability",
            "source": "research",
            "capabilities": ["automation"],
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian") as mock_guardian:
            mock_guardian.validate_code_for_safety.return_value = (False, "Dangerous code detected")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.integrate_ability(ability)
            assert result is False

    def test_integrate_reference_ability(self, tmp_path):
        """Test integrating a reference-type ability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        ability = {
            "id": "github_123",
            "type": "github_project",
            "name": "Reference Project",
            "url": "https://github.com/test/project",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.integrate_ability(ability)
            assert result is True

    def test_integrate_handles_exception(self, tmp_path, sample_ability):
        """Test integrate_ability handles exceptions."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        # Create an ability with unknown type to trigger default path
        ability = {
            "id": "unknown_123",
            "type": "unknown_type",
            "name": "Unknown",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Should return True for reference integration
            result = instance.integrate_ability(ability)
            assert result is True


class TestRunAcquisitionCycle:
    """Test run_acquisition_cycle method."""

    def test_run_cycle_discovers_evaluates_acquires(self, tmp_path):
        """Test full acquisition cycle flow."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Free Open Source Model", "url": "https://github.com/test/model", "snippet": "Free"},
        ]

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_providers.generate_text.return_value = "Rating: 8 - Excellent for our goals"
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            assert "discovered" in result
            assert "evaluated" in result
            assert "acquired" in result
            assert "integrated" in result
            assert "total_abilities" in result
            assert result["restart_needed"] is False

    def test_run_cycle_triggers_restart_for_high_rating(self, tmp_path):
        """Test that high-rated abilities trigger restart signal."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Amazing Free LLM Model", "url": "https://github.com/test/model", "snippet": "Revolutionary"},
        ]

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_providers.generate_text.return_value = "Rating: 9 - Perfect for crypto trading!"
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            assert result["restart_needed"] is True
            assert "reason" in result

    def test_run_cycle_filters_low_rated_abilities(self, tmp_path):
        """Test that low-rated abilities are not acquired."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Low Quality Model", "url": "https://example.com", "snippet": "Not useful"},
        ]

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_providers.generate_text.return_value = "Rating: 2 - Not relevant"
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            # Low ratings shouldn't be acquired
            assert result["acquired"] == 0


class TestGetStatus:
    """Test get_status method."""

    def test_get_status_returns_correct_structure(self, acquisition_instance):
        """Test status returns expected structure."""
        status = acquisition_instance.get_status()

        assert "total_abilities" in status
        assert "total_models" in status
        assert "categories" in status
        assert "recent_acquisitions" in status
        assert "available_models" in status

    def test_get_status_counts_abilities(self, tmp_path):
        """Test status correctly counts abilities."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Add some abilities
            instance.abilities["acquired"] = [
                {"id": "1", "capabilities": ["reasoning"]},
                {"id": "2", "capabilities": ["coding"]},
                {"id": "3", "capabilities": ["reasoning", "coding"]},
            ]
            instance.models["installed"] = ["model1", "model2"]

            status = instance.get_status()

            assert status["total_abilities"] == 3
            assert status["total_models"] == 2

    def test_get_status_returns_recent_acquisitions(self, tmp_path):
        """Test status returns only recent acquisitions."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Add more than 5 abilities
            for i in range(10):
                instance.abilities["acquired"].append({"id": f"ability_{i}"})

            status = instance.get_status()

            # Should only return last 5
            assert len(status["recent_acquisitions"]) == 5
            assert status["recent_acquisitions"][0]["id"] == "ability_5"


class TestGlobalSingleton:
    """Test global singleton management."""

    def test_get_ability_acquisition_returns_singleton(self, tmp_path):
        """Test get_ability_acquisition returns singleton instance."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            # Reset global state
            import core.ability_acquisition as module
            module._acquisition = None

            instance1 = module.get_ability_acquisition()
            instance2 = module.get_ability_acquisition()

            assert instance1 is instance2

    def test_get_ability_acquisition_creates_new_instance(self, tmp_path):
        """Test get_ability_acquisition creates instance when None."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            import core.ability_acquisition as module
            module._acquisition = None

            instance = module.get_ability_acquisition()

            assert instance is not None
            assert isinstance(instance, module.AbilityAcquisition)


class TestCapabilityDetection:
    """Test capability detection in _acquire_researched_ability."""

    def test_detects_reasoning_capability(self, tmp_path):
        """Test detection of reasoning capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Logic Reasoning Tool",
            "url": "https://example.com",
            "snippet": "A tool for logical reasoning and thinking",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "reasoning" in acquired["capabilities"]

    def test_detects_coding_capability(self, tmp_path):
        """Test detection of coding capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Code Generator",
            "url": "https://example.com",
            "snippet": "A programming and scripting tool",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "coding" in acquired["capabilities"]

    def test_detects_conversation_capability(self, tmp_path):
        """Test detection of conversation capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Chat Bot",
            "url": "https://example.com",
            "snippet": "A conversational chat and talk assistant",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "conversation" in acquired["capabilities"]

    def test_detects_analysis_capability(self, tmp_path):
        """Test detection of analysis capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Data Analyzer",
            "url": "https://example.com",
            "snippet": "Analyze and understand complex data",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "analysis" in acquired["capabilities"]

    def test_detects_automation_capability(self, tmp_path):
        """Test detection of automation capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Auto Agent",
            "url": "https://example.com",
            "snippet": "An autonomous agent for automation",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "automation" in acquired["capabilities"]

    def test_defaults_to_general_capability(self, tmp_path):
        """Test that abilities with no keywords get general capability."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Mystery Tool",
            "url": "https://example.com",
            "snippet": "Something without keywords",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            instance.acquire_ability(discovery)

            acquired = instance.abilities["acquired"][0]
            assert "general" in acquired["capabilities"]


class TestOpenSourceSources:
    """Test OPEN_SOURCE_SOURCES constant."""

    def test_sources_structure(self):
        """Test that OPEN_SOURCE_SOURCES has expected structure."""
        from core.ability_acquisition import OPEN_SOURCE_SOURCES

        assert "huggingface" in OPEN_SOURCE_SOURCES
        assert "github" in OPEN_SOURCE_SOURCES
        assert "ollama" in OPEN_SOURCE_SOURCES

        for source, config in OPEN_SOURCE_SOURCES.items():
            assert "base_url" in config
            assert "focus" in config

    def test_huggingface_source(self):
        """Test HuggingFace source configuration."""
        from core.ability_acquisition import OPEN_SOURCE_SOURCES

        hf = OPEN_SOURCE_SOURCES["huggingface"]
        assert "huggingface.co" in hf["base_url"]
        assert "text-generation" in hf["focus"]

    def test_github_source(self):
        """Test GitHub source configuration."""
        from core.ability_acquisition import OPEN_SOURCE_SOURCES

        gh = OPEN_SOURCE_SOURCES["github"]
        assert "github.com" in gh["base_url"]
        assert "llm" in gh["focus"]

    def test_ollama_source(self):
        """Test Ollama source configuration."""
        from core.ability_acquisition import OPEN_SOURCE_SOURCES

        ol = OPEN_SOURCE_SOURCES["ollama"]
        assert "ollama.com" in ol["base_url"]
        assert "chat" in ol["focus"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_discovery_list(self, tmp_path):
        """Test handling empty discovery results."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = []

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            assert result["discovered"] == 0
            assert result["acquired"] == 0

    def test_corrupted_abilities_file(self, tmp_path):
        """Test handling corrupted abilities file."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        # Write corrupted JSON
        with open(abilities_path / "abilities.json", "w") as f:
            f.write("not valid json {{{")

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition

            # Should raise JSONDecodeError
            with pytest.raises(json.JSONDecodeError):
                instance = AbilityAcquisition()

    def test_missing_discovery_fields(self, tmp_path):
        """Test handling discoveries with missing fields."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        # Discovery missing most fields
        discovery = {"source": "web_search"}

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            mock_providers.generate_text.return_value = "Rating: 5"

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Should not raise
            result = instance.evaluate_ability(discovery)
            assert "rating" in result

    def test_very_long_snippet(self, tmp_path):
        """Test handling very long snippet text."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Test",
            "url": "https://example.com",
            "snippet": "A" * 10000,  # Very long snippet
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            # Should handle gracefully
            result = instance.acquire_ability(discovery)
            assert result is True

    def test_special_characters_in_title(self, tmp_path):
        """Test handling special characters in ability title."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Test Model <script>alert('xss')</script> & Special",
            "url": "https://example.com",
            "snippet": "Test",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)
            assert result is True

    def test_unicode_in_content(self, tmp_path):
        """Test handling unicode characters in content."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        discovery = {
            "source": "web_search",
            "title": "Japanese: ichi ni san shichi hachi kyu ju",
            "url": "https://example.com",
            "snippet": "Chinese: yi er san qi ba jiu shi - Korean: hana dul set il chil pal gu sip",
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.acquire_ability(discovery)
            assert result is True
            instance._save_abilities()

            # Verify file was written correctly
            with open(abilities_path / "abilities.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
            assert len(saved["acquired"]) == 1


class TestAdditionalCoverage:
    """Additional tests to cover remaining branches."""

    def test_ollama_discovery_non_200_response(self, tmp_path):
        """Test Ollama discovery with non-200 response code."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = []

        mock_response = MagicMock()
        mock_response.status_code = 404  # Non-200 response

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_requests_get.return_value = mock_response

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            discoveries = instance.discover_open_source_models()

            # No Ollama models should be added with non-200 response
            ollama_discoveries = [d for d in discoveries if d.get("source") == "ollama"]
            assert len(ollama_discoveries) == 0

    def test_evaluate_rating_not_found_in_response(self, tmp_path, sample_discovery):
        """Test evaluation when no numeric rating is in the response."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            # Response with no valid rating number
            mock_providers.generate_text.return_value = "This is good but I am not sure of a number."

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            # Should default to rating 5
            assert result["rating"] == 5

    def test_evaluate_with_number_outside_range(self, tmp_path, sample_discovery):
        """Test evaluation when rating number is outside 1-10 range."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"):
            # Response with number outside valid range (11, 15, 0)
            mock_providers.generate_text.return_value = "Score: 15 out of 20, or maybe 11 percent."

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()
            result = instance.evaluate_ability(sample_discovery)

            # Should default to rating 5 since 15 and 11 are > 10
            assert result["rating"] == 5

    def test_ollama_subprocess_exception_during_version_check(self, tmp_path, sample_ollama_discovery):
        """Test Ollama acquisition when subprocess raises exception on version check."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            # Simulate FileNotFoundError (Ollama not installed)
            mock_subprocess.run.side_effect = FileNotFoundError("ollama not found")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(sample_ollama_discovery, "test_id")
            assert result is False

    def test_ollama_subprocess_timeout(self, tmp_path, sample_ollama_discovery):
        """Test Ollama acquisition when pull times out."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        import subprocess as real_subprocess

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("core.ability_acquisition.subprocess") as mock_subprocess:
            # Version check succeeds, pull times out
            mock_subprocess.run.side_effect = [
                MagicMock(returncode=0),  # version check
                real_subprocess.TimeoutExpired("ollama", 300),  # pull timeout
            ]

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance._acquire_ollama_model(sample_ollama_discovery, "test_id")
            assert result is False

    def test_integrate_ability_exception_handling(self, tmp_path):
        """Test integrate_ability when an unexpected exception occurs."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        ability = {
            "id": "research_123",
            "type": "researched_ability",
            "name": "Test Ability",
            "source": "research",
            "capabilities": ["reasoning"],
        }

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine"), \
             patch("core.ability_acquisition.providers"), \
             patch("core.ability_acquisition.evolution") as mock_evolution, \
             patch("core.ability_acquisition.guardian") as mock_guardian:
            mock_guardian.validate_code_for_safety.side_effect = Exception("Unexpected error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.integrate_ability(ability)
            assert result is False

    def test_run_cycle_integration_after_acquire(self, tmp_path):
        """Test that integration happens after acquisition in cycle."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Great Open Source Model", "url": "https://github.com/test/model", "snippet": "Amazing free tool"},
        ]

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_providers.generate_text.return_value = "Rating: 7 - Good for our goals"
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            # Should have acquired and integrated
            assert result["acquired"] > 0
            assert result["integrated"] > 0

    def test_run_cycle_multiple_discoveries(self, tmp_path):
        """Test cycle with multiple discoveries of varying quality."""
        abilities_path = tmp_path / "data" / "abilities"
        models_path = tmp_path / "data" / "models"
        log_path = tmp_path / "data" / "ability_acquisitions.log"

        abilities_path.mkdir(parents=True, exist_ok=True)
        models_path.mkdir(parents=True, exist_ok=True)

        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"title": "Free LLM Model 1", "url": "https://github.com/test/model1", "snippet": "Good"},
            {"title": "Free LLM Model 2", "url": "https://github.com/test/model2", "snippet": "Better"},
            {"title": "Free LLM Model 3", "url": "https://github.com/test/model3", "snippet": "Best"},
        ]

        rating_sequence = iter(["Rating: 8", "Rating: 6", "Rating: 9"])

        with patch("core.ability_acquisition.ABILITIES_PATH", abilities_path), \
             patch("core.ability_acquisition.MODELS_PATH", models_path), \
             patch("core.ability_acquisition.ACQUISITION_LOG_PATH", log_path), \
             patch("core.ability_acquisition.research_engine") as mock_research, \
             patch("core.ability_acquisition.providers") as mock_providers, \
             patch("core.ability_acquisition.evolution"), \
             patch("core.ability_acquisition.guardian"), \
             patch("requests.get") as mock_requests_get:
            mock_research.get_research_engine.return_value = mock_engine
            mock_providers.generate_text.side_effect = lambda *args, **kwargs: next(rating_sequence, "Rating: 5")
            mock_requests_get.side_effect = Exception("Network error")

            from core.ability_acquisition import AbilityAcquisition
            instance = AbilityAcquisition()

            result = instance.run_acquisition_cycle()

            # Should evaluate multiple and acquire those with rating >= 6
            assert result["evaluated"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
