"""Optional Streamlit integration test for regeneration in the same session."""

from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from terrainweave import studio


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit is optional")
class StreamlitSessionTests(unittest.TestCase):
    def test_two_sessions_do_not_overwrite_each_others_uploads(self) -> None:
        from streamlit.testing.v1 import AppTest

        if not hasattr(AppTest, "file_uploader"):
            self.skipTest("This Streamlit version has no file-uploader testing API")
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {"TERRAINWEAVE_WORKSPACE": temporary}),
        ):
            sessions = []
            uploads = []
            with patch("time.strftime", return_value="run_same_second"):
                for value in (70, 150):
                    buffer = io.BytesIO()
                    Image.new("RGB", (32, 32), (value, 100, 55)).save(buffer, format="PNG")
                    uploads.append(buffer.getvalue())
                    at = AppTest.from_file(studio.__file__, default_timeout=60).run()
                    at.file_uploader[0].set_value(("landscape.png", uploads[-1], "image/png"))
                    next(w for w in at.slider if w.label == "Search effort").set_value(8)
                    at.run()
                    next(
                        w for w in at.button if w.label == "Generate TerrainWeave pattern"
                    ).click().run()
                    self.assertFalse(at.exception)
                    sessions.append(Path(at.session_state["latest_run"]["input_dir"]))
            self.assertEqual((sessions[0] / "reference_01.png").read_bytes(), uploads[0])
            self.assertNotEqual(sessions[0], sessions[1])

    def test_regeneration_discards_the_previous_human_test(self) -> None:
        from streamlit.testing.v1 import AppTest

        if not hasattr(AppTest, "file_uploader"):
            self.skipTest("This Streamlit version has no file-uploader testing API")
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {"TERRAINWEAVE_WORKSPACE": temporary}),
        ):
            buffer = io.BytesIO()
            pixels = np.random.default_rng(42).integers(40, 180, (32, 32, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(buffer, format="PNG")
            at = AppTest.from_file(studio.__file__, default_timeout=60).run()
            at.file_uploader[0].set_value(("landscape.png", buffer.getvalue(), "image/png"))
            next(w for w in at.slider if w.label == "Search effort").set_value(8)
            at.run()
            next(w for w in at.button if w.label == "Generate TerrainWeave pattern").click().run()
            self.assertFalse(at.exception)
            at.session_state["human_test_html"] = "<html>Previous pattern test</html>"
            next(w for w in at.selectbox if w.label == "Target environment").set_value("snow").run()
            next(w for w in at.button if w.label == "Generate TerrainWeave pattern").click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["latest_run"]["environment"], "snow")
            self.assertFalse(at.session_state.get("human_test_html"))


if __name__ == "__main__":
    unittest.main()
