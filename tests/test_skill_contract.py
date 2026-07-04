import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter_is_minimal_and_named(self):
        self.assertTrue(self.skill.startswith("---\n"))
        self.assertRegex(self.skill, r"\nname:\s*bingbingxiaomei-framework\n")
        # V2 description is a YAML block scalar (|)
        self.assertRegex(self.skill, r"description:\s*\|")

    def test_default_persona_is_bottom_logic(self):
        # V2 身份卡和表达 DNA 承载了角色定义
        required = ["第一人称", "冰冰小美", "证据等级", "反证"]
        for phrase in required:
            self.assertIn(phrase, self.skill)

    def test_current_market_requires_live_verification(self):
        required = ["当前市场", "联网核验", "现实事实", "失效条件"]
        for phrase in required:
            self.assertIn(phrase, self.skill)

    def test_no_unconditional_trade_instruction_language(self):
        forbidden_patterns = [
            r"必涨",
            r"保证收益",
            r"无条件买入",
            r"直接满仓",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.skill), pattern)


if __name__ == "__main__":
    unittest.main()
