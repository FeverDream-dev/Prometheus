"""Website contract and accessibility tests (Milestone 2).

These tests read the canonical install commands from ``website/commands.json``
and assert that ``website/index.html`` renders the same command for every OS
tab. They also check internal links resolve, the support matrix mentions WSL,
no trackers / external script origins are present, the reduced-motion media
query exists, and the repo URL is ``FeverDream-dev/Prometheus`` everywhere.

A small stdlib DOM builder (no third-party HTML parser) is used so the suite
stays inside the existing pytest dependency set.
"""

from __future__ import annotations

import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

# commands.json is the single source of truth for the public install commands.
REPO = "FeverDream-dev/Prometheus"
POSIX_ONE_LINER = (
    "curl -fsSL https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh | sh"
)
WINDOWS_ONE_LINER = (
    "irm https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.ps1 | iex"
)

_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []  # list of _Node | str


class _DOMBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, {k: (v if v is not None else "") for k, v in attrs})
        self._stack[-1].children.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = _Node(tag, {k: (v if v is not None else "") for k, v in attrs})
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        self._stack[-1].children.append(data)


def parse_html(text):
    builder = _DOMBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def walk(node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from walk(child)


def find_all(root, *, tag=None, class_=None, attrs=None):
    matches = []
    for node in walk(root):
        if tag is not None and node.tag != tag:
            continue
        if class_ is not None and class_ not in node.attrs.get("class", "").split():
            continue
        if attrs is not None:
            if any(node.attrs.get(k) != v for k, v in attrs.items()):
                continue
        matches.append(node)
    return matches


def text_of(node):
    parts = []

    def collect(n):
        for child in n.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                collect(child)

    collect(node)
    return "".join(parts).strip()


class WebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent
        cls.website_dir = cls.root_dir / "website"
        cls.index_path = cls.website_dir / "index.html"
        cls.css_path = cls.website_dir / "assets" / "css" / "styles.css"
        cls.js_path = cls.website_dir / "assets" / "js" / "install.js"
        cls.commands_path = cls.website_dir / "commands.json"
        cls.pages_wf_path = cls.root_dir / ".github" / "workflows" / "pages.yml"
        cls.index_html = cls.index_path.read_text(encoding="utf-8")
        cls.css = cls.css_path.read_text(encoding="utf-8")
        cls.js = cls.js_path.read_text(encoding="utf-8")
        cls.commands = json.loads(cls.commands_path.read_text(encoding="utf-8"))
        cls.pages_wf = cls.pages_wf_path.read_text(encoding="utf-8")
        cls.dom = parse_html(cls.index_html)

    # -- commands.json: the canonical contract --------------------------------

    def test_commands_repo_owner(self):
        self.assertEqual(self.commands["repo"], REPO)

    def test_commands_tabs_present(self):
        ids = [tab["id"] for tab in self.commands["tabs"]]
        self.assertEqual(ids, ["linux", "macos", "windows"])

    def test_commands_one_liners_match_fixed_contract(self):
        by_id = {tab["id"]: tab for tab in self.commands["tabs"]}
        self.assertEqual(by_id["linux"]["command"], POSIX_ONE_LINER)
        self.assertEqual(by_id["macos"]["command"], POSIX_ONE_LINER)
        self.assertEqual(by_id["windows"]["command"], WINDOWS_ONE_LINER)

    def test_commands_have_manual_alternative(self):
        for tab in self.commands["tabs"]:
            self.assertTrue(tab.get("manual", "").strip(), tab["id"])
            self.assertIn(REPO, tab["command"])
            self.assertIn(REPO, tab["manual"])

    # -- index.html must not drift from commands.json -------------------------

    def test_each_os_tab_command_matches_json(self):
        by_id = {tab["id"]: tab for tab in self.commands["tabs"]}
        for os_id, tab in by_id.items():
            cmds = find_all(self.dom, class_="cmd", attrs={"data-os": os_id})
            self.assertEqual(len(cmds), 1, f"expected one .cmd for {os_id}")
            cmd = cmds[0]
            self.assertEqual(cmd.attrs.get("data-command"), tab["command"])
            self.assertEqual(text_of(cmd), tab["command"])

    def test_each_os_has_tab_and_panel(self):
        for tab in self.commands["tabs"]:
            os_id = tab["id"]
            tabs = find_all(self.dom, tag="button", attrs={"role": "tab", "data-os": os_id})
            self.assertEqual(len(tabs), 1, f"tab button for {os_id}")
            panels = find_all(
                self.dom, attrs={"role": "tabpanel", "data-os": os_id}
            )
            self.assertEqual(len(panels), 1, f"tabpanel for {os_id}")
            self.assertEqual(tabs[0].attrs.get("aria-controls"), panels[0].attrs.get("id"))
            self.assertEqual(panels[0].attrs.get("aria-labelledby"), tabs[0].attrs.get("id"))

    def test_copy_buttons_present_with_command_data(self):
        buttons = find_all(self.dom, class_="copy-btn")
        self.assertEqual(len(buttons), len(self.commands["tabs"]))
        by_id = {tab["id"]: tab for tab in self.commands["tabs"]}
        for btn in buttons:
            self.assertIn("data-command", btn.attrs)
            self.assertIn("data-copy-target", btn.attrs)
            os_id = btn.attrs.get("data-os")
            self.assertEqual(btn.attrs["data-command"], by_id[os_id]["command"])

    def test_manual_alternative_rendered_per_os(self):
        for tab in self.commands["tabs"]:
            blocks = find_all(self.dom, attrs={"data-manual-os": tab["id"]})
            self.assertTrue(blocks, f"manual block missing for {tab['id']}")

    def test_exactly_one_selected_tab_at_load(self):
        selected = [t for t in find_all(self.dom, attrs={"role": "tab"})
                    if t.attrs.get("aria-selected") == "true"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].attrs.get("data-os"), "linux")

    # -- support matrix -------------------------------------------------------

    def test_support_matrix_mentions_wsl_and_native_unsupported(self):
        support = find_all(self.dom, attrs={"id": "support"})
        self.assertTrue(support)
        text = text_of(support[0])
        self.assertIn("WSL", text)
        self.assertIn("Not supported", text)

    # -- internal links resolve ----------------------------------------------

    def test_internal_links_resolve_to_files(self):
        targets = set()
        for node in walk(self.dom):
            for key in ("href", "src"):
                value = node.attrs.get(key)
                if not value:
                    continue
                targets.add(value)
        for value in targets:
            if value.startswith(("#", "mailto:", "tel:", "data:")):
                continue
            if "://" in value:
                continue
            target = (self.website_dir / value.split("#")[0].split("?")[0]).resolve()
            self.assertTrue(target.exists(), f"unresolved internal link: {value}")

    # -- no trackers / external script origins -------------------------------

    def test_no_insecure_http_origins(self):
        insecure_scheme = "http" + "://"
        for text in (self.index_html, self.css, self.js):
            self.assertNotIn(insecure_scheme, text)

    def test_external_urls_are_only_the_project_repo(self):
        for node in walk(self.dom):
            for key in ("href", "src"):
                value = node.attrs.get(key)
                if value and "://" in value:
                    self.assertTrue(
                        value.startswith(f"https://github.com/{REPO}"),
                        f"unexpected external origin: {value}",
                    )

    def test_only_local_script_and_stylesheet(self):
        scripts = [n.attrs.get("src", "") for n in find_all(self.dom, tag="script")]
        scripts = [s for s in scripts if s]
        self.assertEqual(scripts, ["assets/js/install.js"])
        styles = [n.attrs.get("href", "") for n in find_all(self.dom, tag="link")
                  if n.attrs.get("rel") == "stylesheet"]
        self.assertEqual(styles, ["assets/css/styles.css"])

    # -- accessibility --------------------------------------------------------

    def test_reduced_motion_media_query_present(self):
        self.assertIn("prefers-reduced-motion", self.css)

    def test_focus_visible_styles_present(self):
        self.assertIn(":focus-visible", self.css)

    def test_html_lang_and_viewport(self):
        html_node = find_all(self.dom, tag="html")[0]
        self.assertEqual(html_node.attrs.get("lang"), "en")
        meta_viewport = [
            n for n in find_all(self.dom, tag="meta")
            if n.attrs.get("name") == "viewport"
        ]
        self.assertTrue(meta_viewport)

    def test_skip_link_present(self):
        skips = find_all(self.dom, class_="skip-link")
        self.assertEqual(len(skips), 1)
        self.assertTrue(skips[0].attrs.get("href", "").startswith("#"))

    def test_aria_tablist_structure(self):
        self.assertEqual(len(find_all(self.dom, attrs={"role": "tablist"})), 1)
        self.assertGreaterEqual(len(find_all(self.dom, attrs={"role": "tab"})), 3)
        self.assertGreaterEqual(len(find_all(self.dom, attrs={"role": "tabpanel"})), 3)

    def test_tables_have_captions(self):
        for table in find_all(self.dom, tag="table"):
            captions = [c for c in table.children
                        if isinstance(c, _Node) and c.tag == "caption"]
            self.assertTrue(captions, "every table needs a <caption>")

    # -- repo URL correctness everywhere -------------------------------------

    def test_repo_url_present(self):
        self.assertGreater(self.index_html.count(REPO), 3)

    def test_no_wrong_repo_owner_in_website(self):
        wrong_owner = "prometheus" + "/local-agent"
        for path in (self.index_path, self.css_path, self.js_path, self.commands_path):
            self.assertNotIn(wrong_owner, path.read_text(encoding="utf-8"))

    # -- placeholder discipline (AGENTS.md rule 4 & 5) ------------------------

    def test_provisional_logo_marked_in_comment(self):
        lowered = self.index_html.lower()
        self.assertIn("provisional logo mark", lowered)
        self.assertIn("official", lowered)

    def test_terminal_placeholder_is_labeled(self):
        self.assertIn("PLACEHOLDER", self.index_html)
        self.assertIn("TODO: replace with real terminal recording", self.index_html)

    # -- required content sections -------------------------------------------

    def test_required_section_ids_present(self):
        ids = {"install", "support", "requirements", "installer",
               "first-run", "commands", "troubleshooting"}
        found = {n.attrs.get("id") for n in walk(self.dom) if n.attrs.get("id")}
        self.assertTrue(ids <= found, f"missing sections: {ids - found}")

    def test_quick_commands_documented(self):
        commands_text = text_of(find_all(self.dom, attrs={"id": "commands"})[0])
        for cmd in ("prometheus setup", "prometheus doctor",
                    "prometheus update", "prometheus uninstall"):
            self.assertIn(cmd, commands_text)

    def test_troubleshooting_covers_required_topics(self):
        text = text_of(find_all(self.dom, attrs={"id": "troubleshooting"})[0]).lower()
        for topic in ("path", "ollama", "gpu", "wsl", "permission", "offline"):
            self.assertIn(topic, text)

    def test_installer_disclosure_section_present(self):
        text = text_of(find_all(self.dom, attrs={"id": "installer"})[0]).lower()
        self.assertIn("sha-256", text)
        self.assertIn("uninstall", text)

    def test_first_run_section_present(self):
        text = text_of(find_all(self.dom, attrs={"id": "first-run"})[0]).lower()
        self.assertIn("ollama", text)
        self.assertIn("approve", text)
        self.assertIn("download", text)

    # -- Pages workflow -------------------------------------------------------

    def test_pages_workflow_sources_website_directory(self):
        wf = self.pages_wf
        self.assertIn("actions/configure-pages", wf)
        self.assertIn("actions/upload-pages-artifact", wf)
        self.assertIn("path: ./website", wf)
        self.assertIn("actions/deploy-pages", wf)

    def test_pages_workflow_triggers(self):
        wf = self.pages_wf
        self.assertIn("branches: [main]", wf)
        self.assertIn("workflow_dispatch", wf)


if __name__ == "__main__":
    unittest.main()
