from pathlib import Path
import unittest
from unittest.mock import patch

from pricing_agent.config import DEFAULT_COMPETITORS, DEFAULT_PRODUCTS, PROJECT_DIR, load_environment


class ConfigTests(unittest.TestCase):
    def test_default_data_paths_are_project_relative_absolute_paths(self):
        self.assertTrue(DEFAULT_PRODUCTS.is_absolute())
        self.assertEqual(DEFAULT_PRODUCTS, PROJECT_DIR / "data" / "products.csv")
        self.assertEqual(DEFAULT_COMPETITORS, PROJECT_DIR / "data" / "competitors.csv")

    def test_env_file_uses_project_directory_instead_of_terminal_directory(self):
        with patch("pricing_agent.config.load_dotenv") as load:
            load_environment()
        load.assert_called_once_with(PROJECT_DIR / ".env")
