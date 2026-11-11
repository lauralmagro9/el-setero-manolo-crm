"""Tests for the configuration loader (settings.toml, .env and environment variables)."""

import pytest

from crm.config import load_settings

from tests.utils.seed import write_env


class TestLoadSettings:
    """Tests for load_settings."""

    def test_0_defaults_come_from_settings_toml(self, toml_file, tmp_path):
        """Without .env or variables, the values of settings.toml are used."""
        s = load_settings(toml_file, tmp_path / "missing.env", environ={})
        assert s.services.groq_api == "from-toml"
        assert s.database.url == "sqlite:///default.db"

    def test_1_env_file_overrides_toml(self, toml_file, tmp_path):
        """A key defined in .env replaces the default; the others keep theirs."""
        env = write_env(tmp_path, "SERVICES_GROQ_API=sidcsdc...\n")
        s = load_settings(toml_file, env, environ={})
        assert s.services.groq_api == "sidcsdc..."
        assert s.database.url == "sqlite:///default.db"

    def test_2_process_environment_beats_env_file(self, toml_file, tmp_path):
        """A real environment variable has priority over the .env file."""
        env = write_env(tmp_path, "SERVICES_GROQ_API=from-dotenv\n")
        s = load_settings(toml_file, env, environ={"SERVICES_GROQ_API": "from-os"})
        assert s.services.groq_api == "from-os"

    def test_3_database_url_variable(self, toml_file):
        """DATABASE_URL overrides [database] url."""
        s = load_settings(toml_file, None, environ={"DATABASE_URL": "postgresql://x"})
        assert s.database.url == "postgresql://x"

    def test_4_values_are_converted_to_the_default_type(self, toml_file):
        """Text from the environment becomes int, bool or list as in settings.toml."""
        s = load_settings(
            toml_file, None,
            environ={"SERVICES_TIMEOUT": "60", "SERVICES_DEBUG": "true", "SERVICES_TAGS": "x, y"},
        )
        assert s.services.timeout == 60
        assert s.services.debug is True
        assert s.services.tags == ["x", "y"]

    def test_5_invalid_value_raises_clear_error(self, toml_file):
        """A value that cannot be converted raises an error naming the variable."""
        with pytest.raises(ValueError, match="SERVICES_TIMEOUT"):
            load_settings(toml_file, None, environ={"SERVICES_TIMEOUT": "much"})

    def test_6_unknown_variable_ignored_and_missing_key_fails(self, toml_file):
        """Unknown variables are ignored; reading a key that does not exist raises."""
        s = load_settings(toml_file, None, environ={"SOMETHING_ELSE": "1"})
        with pytest.raises(AttributeError):
            s.services.does_not_exist
