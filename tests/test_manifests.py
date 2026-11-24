"""プラグインの目印（Claude・Antigravity）とスキルの版・名前がそろっているかのテスト。標準ライブラリの unittest だけで動く。

  python tests/test_manifests.py

版を上げるときに直すファイル：.claude-plugin/marketplace.json、plugins/monozukuri/.claude-plugin/plugin.json、
plugins/monozukuri/.antigravity-plugin/plugin.json、各スキルの SKILL.md の metadata.version。
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "monozukuri")
SKILLS = os.path.join(PLUGIN, "skills")
# Antigravity の plugin.json で使える項目（ほかの項目は黙って捨てられる。Antigravity 2.35.0 の組み込みの plugin スキル）
AG_KEYS = {"name", "displayName", "description", "version", "author", "homepage", "repository", "logo",
           "suggestedPrompts", "disabled"}


def load_jsonc(path):
    """コメント（行頭の //）と、閉じかっこの前のカンマを許して読む"""
    with open(path, encoding="utf-8") as f:
        text = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("//"))
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def front_matter(path):
    """SKILL.md の先頭の --- の間から、name と metadata の version を拾う"""
    with open(path, encoding="utf-8") as f:
        head = f.read().split("---", 2)[1]
    name = re.search(r"^name:\s*(\S+)", head, re.M)
    ver = re.search(r"^\s+version:\s*\"?([\d.]+)", head, re.M)
    return (name.group(1) if name else None), (ver.group(1) if ver else None)


class TestManifests(unittest.TestCase):
    def setUp(self):
        self.claude = load_jsonc(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"))
        self.ag = load_jsonc(os.path.join(PLUGIN, ".antigravity-plugin", "plugin.json"))
        market = load_jsonc(os.path.join(ROOT, ".claude-plugin", "marketplace.json"))
        self.market = next(p for p in market["plugins"] if p["name"] == "monozukuri")

    def test_versions_match(self):
        want = self.claude["version"]
        self.assertEqual(self.market["version"], want, "marketplace.json")
        self.assertEqual(self.ag.get("version"), want, ".antigravity-plugin/plugin.json")
        for skill in sorted(os.listdir(SKILLS)):
            md = os.path.join(SKILLS, skill, "SKILL.md")
            if os.path.isfile(md):
                self.assertEqual(front_matter(md)[1], want, f"{skill}/SKILL.md の metadata.version")

    def test_antigravity_manifest(self):
        # agy plugin install はコメントの無い JSON しか読めない（agy plugin validate の警告。agy 1.5.16）
        with open(os.path.join(PLUGIN, ".antigravity-plugin", "plugin.json"), encoding="utf-8") as f:
            json.load(f)
        self.assertEqual(set(self.ag) - AG_KEYS, set(), "Antigravity が読まない項目がある")
        self.assertEqual(self.ag["name"], self.claude["name"])
        self.assertEqual(self.ag["description"], self.claude["description"])
        self.assertLessEqual(len(self.ag.get("suggestedPrompts", [])), 3)

    def test_skill_names_match_folders(self):
        # Antigravity・Gemini CLI・Gemini アプリは、name をフォルダ名と同じ（小文字とハイフン）にする決まり
        skills = [s for s in sorted(os.listdir(SKILLS)) if os.path.isfile(os.path.join(SKILLS, s, "SKILL.md"))]
        self.assertEqual(len(skills), 3)
        for skill in skills:
            name, _ = front_matter(os.path.join(SKILLS, skill, "SKILL.md"))
            self.assertEqual(name, skill)
            self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
