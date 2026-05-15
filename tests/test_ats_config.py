from pathlib import Path

from services import ats_config


def test_ats_length_profile_can_be_loaded_from_config(tmp_path, monkeypatch):
    config_path = tmp_path / "ats_config.yaml"
    config_path.write_text(
        """
weights:
  skills: 0.4
  keywords: 0.2
  format: 0.2
  experience: 0.2

length_profile:
  ideal_min_words: 100
  ideal_max_words: 500
  extended_max_words: 900
  very_long_max_words: 1400
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("ATS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(ats_config, "_cached_length_profile", None)

    profile = ats_config.get_ats_length_profile()

    assert profile["ideal_min_words"] == 100
    assert profile["very_long_max_words"] == 1400


def test_invalid_ats_length_profile_falls_back(tmp_path, monkeypatch):
    config_path = Path(tmp_path) / "ats_config.yaml"
    config_path.write_text(
        """
length_profile:
  ideal_min_words: 500
  ideal_max_words: 100
  extended_max_words: 90
  very_long_max_words: 80
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("ATS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(ats_config, "_cached_length_profile", None)

    profile = ats_config.get_ats_length_profile()

    assert profile["ideal_min_words"] < profile["ideal_max_words"]
