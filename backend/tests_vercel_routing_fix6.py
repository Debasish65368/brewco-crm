"""
Automated Verification Tests for Fix 6:
Vercel SPA Deep-Link Refreshes & Client-Side Routing Configuration.

Verifies:
1. Valid JSON Syntax:
   - `frontend/vercel.json` parses as valid JSON without errors.
2. Build Configuration Integrity:
   - `buildCommand` is preserved as 'npm run build'.
   - `outputDirectory` is preserved as 'dist'.
3. SPA Rewrite Rules:
   - `rewrites` contains the catch-all rule matching '/(.*)' to '/index.html'.
   - The rewrite regex matches all client routes: '/', '/customers', '/segments', '/campaigns', and deep links.
4. No Duplicate/Conflicting Configurations:
   - Asserts there is no duplicate or conflicting `vercel.json` at the workspace root.
5. Entry Document & Asset Accessibility:
   - Validates that `frontend/index.html` exists and defines the root DOM node and script entry point.
6. React Client-Side Route Integrity:
   - Validates that `frontend/src/App.jsx` defines `<BrowserRouter>`, `<Routes>`, and `<Route>` entries
     for '/', '/customers', '/segments', and '/campaigns' mapping to their respective page components.
"""

import json
import os
import re
import sys
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(workspace_root, "frontend")


class TestVercelConfiguration(unittest.TestCase):
    """Verifies Vercel deployment configuration correctness and SPA routing support."""

    def setUp(self):
        self.vercel_json_path = os.path.join(frontend_dir, "vercel.json")
        self.root_vercel_path = os.path.join(workspace_root, "vercel.json")
        self.entry_html_path = os.path.join(frontend_dir, "index.html")
        self.app_jsx_path = os.path.join(frontend_dir, "src", "App.jsx")

    def test_vercel_json_exists_and_is_valid_json(self):
        """frontend/vercel.json must exist and parse cleanly as JSON."""
        self.assertTrue(
            os.path.exists(self.vercel_json_path),
            f"frontend/vercel.json not found at {self.vercel_json_path}",
        )

        with open(self.vercel_json_path, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except Exception as e:
                self.fail(f"frontend/vercel.json failed to parse as JSON: {e}")

        self.assertIsInstance(config, dict, "vercel.json root must be a JSON object.")

    def test_build_configuration_preserved(self):
        """Existing build command and output directory must be preserved."""
        with open(self.vercel_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.assertEqual(
            config.get("buildCommand"),
            "npm run build",
            "buildCommand must remain 'npm run build'",
        )
        self.assertEqual(
            config.get("outputDirectory"),
            "dist",
            "outputDirectory must remain 'dist'",
        )

    def test_spa_rewrite_rule_present_and_correct(self):
        """Vercel configuration must specify an SPA catch-all rewrite to /index.html."""
        with open(self.vercel_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.assertIn("rewrites", config, "vercel.json must include a 'rewrites' array.")
        rewrites = config["rewrites"]
        self.assertIsInstance(rewrites, list, "'rewrites' must be an array.")
        self.assertGreater(len(rewrites), 0, "'rewrites' array must not be empty.")

        # Find catch-all SPA rewrite
        spa_rule = next(
            (r for r in rewrites if r.get("source") in ("/(.*)", "/[^.]*") and r.get("destination") == "/index.html"),
            None,
        )
        self.assertIsNotNone(
            spa_rule,
            "vercel.json must have a rewrite rule matching '/(.*)' to '/index.html'",
        )
        self.assertEqual(spa_rule.get("source"), "/(.*)")
        self.assertEqual(spa_rule.get("destination"), "/index.html")

    def test_rewrite_pattern_matches_all_spa_routes(self):
        """The rewrite source regex must match top-level and deep-link SPA routes."""
        with open(self.vercel_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        source_pattern = config["rewrites"][0]["source"]
        # Convert Vercel source pattern to Python regex
        regex_pattern = f"^{source_pattern}$"

        test_routes = [
            "/",
            "/customers",
            "/segments",
            "/campaigns",
            "/customers/123",
            "/campaigns/new",
            "/settings/profile",
        ]
        for route in test_routes:
            self.assertTrue(
                bool(re.match(regex_pattern, route)),
                f"Pattern {source_pattern!r} must match client-side route {route!r}",
            )

    def test_no_conflicting_root_vercel_json(self):
        """Workspace root must not contain a conflicting vercel.json that could override frontend/."""
        self.assertFalse(
            os.path.exists(self.root_vercel_path),
            "Conflicting vercel.json found at workspace root. "
            "Only frontend/vercel.json should be present to avoid deployment ambiguity.",
        )

    def test_entry_document_exists_and_contains_spa_anchor(self):
        """frontend/index.html must exist and contain the root div for React hydration."""
        self.assertTrue(os.path.exists(self.entry_html_path), "frontend/index.html must exist.")
        with open(self.entry_html_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('id="root"', content, "index.html must contain id='root' mounting element.")
        self.assertIn("src/main.jsx", content, "index.html must include script tag for src/main.jsx.")

    def test_react_routes_defined_in_app_jsx(self):
        """frontend/src/App.jsx must define client-side routes for Dashboard, Customers, Segments, and Campaigns."""
        self.assertTrue(os.path.exists(self.app_jsx_path), "frontend/src/App.jsx must exist.")
        with open(self.app_jsx_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("BrowserRouter", content, "App.jsx must use BrowserRouter.")
        self.assertIn("Routes", content, "App.jsx must define Routes.")

        expected_routes = {
            "/": "DashboardPage",
            "/customers": "CustomersPage",
            "/segments": "SegmentsPage",
            "/campaigns": "CampaignsPage",
        }

        for path, component in expected_routes.items():
            pattern = rf'path=["\']{re.escape(path)}["\']\s+element=\{{<{component}\s*/?>\}}'
            self.assertTrue(
                bool(re.search(pattern, content)),
                f"App.jsx must define route for {path!r} with element <{component} />",
            )


if __name__ == "__main__":
    unittest.main()
