"""R17 release-readiness: detect malformed Python sources before Qt/QA jobs."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class R17SourceIntegrityTests(unittest.TestCase):
    def test_python_sources_parse_without_syntax_errors(self):
        """Catch escaped-newline corruption that broke R4/R14/R16 CI."""
        sources = sorted((ROOT / "drawtemp").rglob("*.py"))
        self.assertGreater(len(sources), 50)
        for path in sources:
            with self.subTest(source=path.relative_to(ROOT).as_posix()):
                ast.parse(path.read_text(encoding="utf-8-sig"),
                          filename=str(path))


if __name__ == "__main__":
    unittest.main()
