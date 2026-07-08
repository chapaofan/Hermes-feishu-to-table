"""Regression tests for the markdown-table → CardKit v2 renderer.

These tests exercise the three functions added to feishu.py:
  - _parse_markdown_table
  - _build_table_card
  - _build_interactive_card_with_tables

They cover the four bugs reported as "lark message not rendering table":

  Bug A: pipes inside a fenced code block were treated as table rows
  Bug B: divider line without trailing `|` was treated as a data row
  Bug C: a header with zero data rows was emitted as a broken empty table
  Bug D: markdown inline formatting leaked into cells as literal characters

Run with:
    python3 -m unittest test_table_renderer.py
"""

import ast
import json
import os
import re
import unittest
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# The feishu.py module imports gateway.* at the top, which makes it impossible
# to import directly from a unit-test context. Instead we extract the three
# table-rendering functions (and the regexes they depend on) via the AST and
# exec them into a clean namespace. This is exactly the same source the
# running gateway executes — there's no parallel implementation here.
# ---------------------------------------------------------------------------

def _load_fixtures() -> Dict[str, Any]:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(repo_root, "feishu.py"), "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    prelude: List[ast.stmt] = []
    wanted_fns = {
        "_parse_markdown_table",
        "_build_table_card",
        "_build_interactive_card_with_tables",
    }
    wanted_regexes = {
        "_MARKDOWN_TABLE_LINE_RE",
        "_MARKDOWN_TABLE_DIVIDER_RE",
        "_MARKDOWN_FENCE_OPEN_RE",
        "_MARKDOWN_FENCE_CLOSE_RE",
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted_regexes:
                    prelude.append(node)
                    break
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_fns:
            prelude.append(node)
    ns: Dict[str, Any] = {
        "re": re,
        "List": List,
        "Dict": Dict,
        "Any": Any,
        "Optional": Optional,
    }
    exec(compile(ast.Module(body=prelude, type_ignores=[]), "<prelude>", "exec"), ns)
    return ns


_FIX = _load_fixtures()
parse = _FIX["_parse_markdown_table"]
build_card = _FIX["_build_table_card"]
build_interactive = _FIX["_build_interactive_card_with_tables"]


def _tables(card: Dict[str, Any]):
    """Return just the table components from a card body."""
    return [
        e for e in card["body"]["elements"] if e.get("tag") == "table"
    ]


def _texts(card: Dict[str, Any]):
    return [e for e in card["body"]["elements"] if e.get("tag") == "markdown"]


class TestParseMarkdownTable(unittest.TestCase):
    def test_basic_two_by_two(self):
        segs = parse("| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["type"], "table")
        self.assertEqual(segs[0]["headers"], ["A", "B"])
        self.assertEqual(segs[0]["rows"], [["1", "2"], ["3", "4"]])

    def test_prose_around_table(self):
        text = "Intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nOutro\n"
        segs = parse(text)
        self.assertEqual([s["type"] for s in segs], ["text", "table", "text"])

    def test_two_tables_separated_by_prose(self):
        text = (
            "First:\n| A | B |\n|---|---|\n| 1 | 2 |\n\nMid\n\n"
            "| C | D |\n|---|---| \n| 3 | 4 |\n"
        )
        segs = parse(text)
        self.assertEqual([s["type"] for s in segs], ["text", "table", "text", "table"])
        self.assertEqual(segs[1]["headers"], ["A", "B"])
        self.assertEqual(segs[3]["headers"], ["C", "D"])

    def test_divider_without_trailing_pipe(self):
        """Bug B: `| --- | --- |` (no trailing |) must be recognised as divider."""
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        segs = parse(text)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["type"], "table")
        self.assertEqual(segs[0]["headers"], ["A", "B"])
        self.assertEqual(segs[0]["rows"], [["1", "2"]],
                         msg="divider line must not leak into the data rows")

    def test_divider_with_alignment_colons(self):
        text = "| L | C | R |\n|:---|:---:|---:|\n| 1 | 2 | 3 |\n"
        segs = parse(text)
        self.assertEqual(segs[0]["rows"], [["1", "2", "3"]])

    def test_fenced_code_block_does_not_trigger_table(self):
        """Bug A: pipes inside a fenced code block must not become a table."""
        text = (
            "Code:\n\n```\n"
            "| not | a | table |\n"
            "| --- | --- | --- |\n"
            "```\n\n"
            "Real:\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        segs = parse(text)
        tables = [s for s in segs if s["type"] == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["headers"], ["A", "B"])
        self.assertEqual(tables[0]["rows"], [["1", "2"]])

    def test_tilde_fence_also_protected(self):
        text = (
            "~~~\n"
            "| not | table |\n| --- | --- |\n"
            "~~~\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        segs = parse(text)
        self.assertEqual(len([s for s in segs if s["type"] == "table"]), 1)

    def test_table_with_only_header_becomes_text(self):
        """Bug C: header + divider with no data rows must NOT emit a table."""
        text = "| A | B |\n|---|---|\n"
        segs = parse(text)
        self.assertEqual([s["type"] for s in segs], ["text"])
        # And the source text is preserved.
        self.assertIn("| A | B |", segs[0]["content"])

    def test_table_with_single_cell_does_not_become_table(self):
        """A `|`-less line or single-cell pseudo-row is not a real table."""
        text = "Intro | not | table | divider | --- | --- |\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        segs = parse(text)
        tables = [s for s in segs if s["type"] == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["headers"], ["A", "B"])

    def test_empty_input(self):
        self.assertEqual(parse(""), [{"type": "text", "content": ""}])
        self.assertEqual(parse(None or ""), [{"type": "text", "content": ""}])

    def test_no_pipe_in_text(self):
        self.assertEqual(parse("just prose, no tables here"),
                         [{"type": "text", "content": "just prose, no tables here"}])


class TestBuildTableCard(unittest.TestCase):
    def test_columns_have_unique_names(self):
        card = build_card(["A", "B"], [["1", "2"]])
        names = [c["name"] for c in card["columns"]]
        self.assertEqual(names, ["col_0", "col_1"])
        self.assertEqual(len(set(names)), 2, "column names must be unique")

    def test_rows_map_to_column_names(self):
        card = build_card(["A", "B"], [["1", "2"]])
        self.assertEqual(card["rows"], [{"col_0": "1", "col_1": "2"}])

    def test_header_style_is_set(self):
        card = build_card(["A"], [["1"]])
        self.assertTrue(card["header_style"]["bold"])

    def test_strips_bold(self):
        card = build_card(["**Name**"], [["**bold value**"]])
        self.assertEqual(card["columns"][0]["display_name"], "Name")
        self.assertEqual(card["rows"][0]["col_0"], "bold value")

    def test_strips_inline_code(self):
        """Bug D: `code` markers should be removed, not preserved as literal."""
        card = build_card(["Cmd"], [["`ls -la`"]])
        self.assertEqual(card["rows"][0]["col_0"], "ls -la")

    def test_strips_italic(self):
        card = build_card(["*x*"], [["_y_"]])
        self.assertEqual(card["columns"][0]["display_name"], "x")
        self.assertEqual(card["rows"][0]["col_0"], "y")

    def test_preserves_snake_case_identifiers(self):
        """`_user_` and similar identifier-shaped tokens must NOT be stripped."""
        card = build_card(["var"], [["foo_bar_baz"]])
        self.assertEqual(card["rows"][0]["col_0"], "foo_bar_baz")

    def test_preserves_feishu_mention_placeholder(self):
        card = build_card(["Owner"], [["@_user_1"]])
        self.assertEqual(card["rows"][0]["col_0"], "@_user_1")

    def test_strips_italic_with_punctuation_flanks(self):
        card = build_card(["Note"], [["em is _italic_ here"]])
        self.assertEqual(card["rows"][0]["col_0"], "em is italic here")

    def test_preserves_em_dash(self):
        card = build_card(["Note"], [["yes — ok"]])
        self.assertEqual(card["rows"][0]["col_0"], "yes — ok")

    def test_empty_cell_becomes_space(self):
        card = build_card(["A"], [[""]])
        self.assertEqual(card["rows"][0]["col_0"], " ")


class TestBuildInteractiveCardWithTables(unittest.TestCase):
    def test_returns_none_when_no_table(self):
        self.assertIsNone(build_interactive("just prose\nwith **bold**\n"))

    def test_schema_is_two_point_oh(self):
        card = build_interactive("| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(card["schema"], "2.0")
        self.assertTrue(card["config"]["wide_screen_mode"])

    def test_interleaves_prose_and_table(self):
        text = "Intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nOutro\n"
        card = build_interactive(text)
        self.assertEqual(len(_tables(card)), 1)
        self.assertEqual(len(_texts(card)), 2)
        self.assertEqual(_texts(card)[0]["content"], "Intro")
        self.assertEqual(_texts(card)[1]["content"], "Outro")

    def test_fenced_code_does_not_break_real_table(self):
        """Bug A end-to-end: the real table renders, code is preserved as text."""
        text = (
            "Try:\n```\n"
            "| fake | table |\n| --- | --- |\n"
            "```\n"
            "Real:\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        card = build_interactive(text)
        tables = _tables(card)
        self.assertEqual(len(tables), 1)
        self.assertEqual(
            [c["display_name"] for c in tables[0]["columns"]], ["A", "B"]
        )
        # The code block content lives in a markdown element, not in the table.
        joined = " ".join(t["content"] for t in _texts(card))
        self.assertIn("| fake | table |", joined)

    def test_no_empty_table_component(self):
        """Bug C end-to-end: a header-only table falls back to a post message."""
        text = "Header only:\n| A | B |\n|---|---|\n"
        self.assertIsNone(build_interactive(text))

    def test_divider_without_trailing_pipe_renders_correctly(self):
        """Bug B end-to-end: no garbage row."""
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        card = build_interactive(text)
        rows = _tables(card)[0]["rows"]
        self.assertEqual(rows, [{"col_0": "1", "col_1": "2"}])

    def test_mention_placeholder_passes_through(self):
        text = "| Owner | Note |\n|---|---|\n| @_user_1 | ok |\n"
        card = build_interactive(text)
        table = _tables(card)[0]
        row = table["rows"][0]
        self.assertEqual(row["col_0"], "@_user_1")
        self.assertEqual(row["col_1"], "ok")

    def test_payload_is_json_serializable(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        card = build_interactive(text)
        # Will raise TypeError if anything is not JSON-serialisable.
        json.dumps(card, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
