"""Tests for checkbox.knowledge: store (FTS5/LIKE), source indexing, search."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox.knowledge import search as search_mod  # noqa: E402
from checkbox.knowledge import source as source_mod  # noqa: E402
from checkbox.knowledge import store  # noqa: E402
from checkbox.profile import Profile  # noqa: E402

STUB_18CE = REPO_ROOT / "tests" / "fixtures" / "stubs" / "odoo18-ce"
STUB_17CE = REPO_ROOT / "tests" / "fixtures" / "stubs" / "odoo17-ce"

# -- source.py ----------------------------------------------------------------


def test_build_indexes_the_manifest():
    docs = source_mod.build([STUB_18CE / "addons"], "18.0")
    titles = [d["title"] for d in docs]
    assert any("Purchase (purchase)" in t for t in titles)


def test_build_indexes_the_settings_field():
    docs = source_mod.build([STUB_18CE / "addons"], "18.0")
    field_docs = [d for d in docs if d["title"] == "res.config.settings.po_order_approval"]
    assert len(field_docs) == 1
    assert "Purchase Order Approval" in field_docs[0]["snippet"]
    assert field_docs[0]["line"] is not None


def test_build_indexes_the_settings_view_help_text():
    # Regression coverage for a real bug hit while building this: the fixture
    # XML's own comment used "--", which is illegal inside an XML comment and
    # silently broke ET.parse -- _setting_view_docs correctly swallows the
    # ParseError (a broken file must not crash indexing), which meant this
    # whole code path produced zero docs with no visible error. This test
    # exists so that ever happening again fails loudly here, not silently in
    # a `checkbox search` that just returns fewer results than expected.
    docs = source_mod.build([STUB_18CE / "addons"], "18.0")
    view_docs = [d for d in docs if d["ref"].endswith("res_config_settings_views.xml")]
    assert view_docs, "settings view XML produced no documents -- check it still parses"
    assert any("Request managers to approve" in d["snippet"] for d in view_docs)


def test_build_indexes_sale_margin_manifest():
    # so-line-margin seed case (docs/ARCHITECTURE.md §11.3): rung 5
    # "module" evidence is the manifest alone.
    docs = source_mod.build([STUB_18CE / "addons"], "18.0")
    titles = [d["title"] for d in docs]
    assert any("Margins in Sales Orders (sale_margin)" in t for t in titles)


def test_build_indexes_dropshipping_setting():
    # dropship seed case: module_stock_dropshipping, a module_* Boolean.
    docs = source_mod.build([STUB_18CE / "addons"], "18.0")
    field_docs = [d for d in docs if d["title"] == "res.config.settings.module_stock_dropshipping"]
    assert len(field_docs) == 1


def test_build_indexes_tax_rounding_setting_17ce():
    # tax-rounding-per-line seed case, 17.0 CE.
    docs = source_mod.build([STUB_17CE / "addons"], "17.0")
    field_docs = [
        d for d in docs if d["title"] == "res.config.settings.tax_calculation_rounding_method"
    ]
    assert len(field_docs) == 1


def test_build_indexes_serial_tracking_setting_17ce():
    # serial-tracking seed case, 17.0 CE.
    docs = source_mod.build([STUB_17CE / "addons"], "17.0")
    field_docs = [d for d in docs if d["title"] == "res.config.settings.group_stock_production_lot"]
    assert len(field_docs) == 1
    assert "Lots & Serial Numbers" in field_docs[0]["snippet"]
    view_docs = [d for d in docs if d["ref"].endswith("res_config_settings_views.xml")]
    assert any("Get a full traceability" in d["snippet"] for d in view_docs)


def test_build_skips_unparseable_manifest(tmp_path):
    addon = tmp_path / "broken_addon"
    addon.mkdir()
    (addon / "__manifest__.py").write_text("{ this is not valid python")
    docs = source_mod.build([tmp_path], "18.0")
    assert docs == []  # tolerated, not crashed


def test_build_empty_roots_returns_empty_list(tmp_path):
    assert source_mod.build([tmp_path / "does-not-exist"], "18.0") == []


def test_iter_relevant_files_prunes_noise_dirs(tmp_path):
    # i18n/static/tests/migrations/__pycache__ can be most of a real
    # addon's files (i18n alone: one .po per language) and never contain
    # a manifest, settings field, or settings view -- both build() and
    # search.py's staleness walk must skip them, or every checkbox search
    # call pays for walking translation files it will never read.
    addon = tmp_path / "mod"
    (addon / "models").mkdir(parents=True)
    (addon / "i18n").mkdir()
    (addon / "static" / "src" / "js").mkdir(parents=True)
    (addon / "models" / "m.py").write_text("# x")
    (addon / "i18n" / "fr.po").write_text("# translation")
    (addon / "static" / "src" / "js" / "f.js").write_text("// x")

    found = {p.name for p in source_mod.iter_relevant_files(addon)}
    assert found == {"m.py"}


# -- store.py -------------------------------------------------------------------

_SAMPLE_DOCS = [
    {
        "kind": "source",
        "ref": "addons/purchase/models/res_config_settings.py",
        "line": 12,
        "title": "res.config.settings.po_order_approval",
        "snippet": "Purchase Order Approval",
        "version": "18.0",
    },
    {
        "kind": "source",
        "ref": "addons/sale/__manifest__.py",
        "line": None,
        "title": "Sales (sale)",
        "snippet": "Sales orders and quotations",
        "version": "18.0",
    },
]


def test_store_index_and_search_fts5(tmp_path):
    con = store.connect(tmp_path / "index.sqlite")
    store.index_documents(con, _SAMPLE_DOCS)
    results = store.search(con, "purchase approval")
    con.close()
    assert results
    assert results[0]["title"] == "res.config.settings.po_order_approval"


def test_store_search_like_fallback(tmp_path, monkeypatch):
    # Force the LIKE path regardless of what this Python build's sqlite3
    # actually supports, per ARCHITECTURE.md §7.2: "the core checks this at
    # runtime" -- both paths need real coverage, not just whichever one the
    # CI machine happens to have compiled in.
    monkeypatch.setattr(store, "has_fts5", lambda: False)
    con = store.connect(tmp_path / "index_like.sqlite")
    store.index_documents(con, _SAMPLE_DOCS)
    results = store.search(con, "purchase")
    con.close()
    assert results
    assert all(r["score"] == 1.0 for r in results)  # LIKE path's flat score


def test_store_search_no_match_returns_empty(tmp_path):
    con = store.connect(tmp_path / "index.sqlite")
    store.index_documents(con, _SAMPLE_DOCS)
    results = store.search(con, "nonexistent_zzz_query")
    con.close()
    assert results == []


def test_store_search_does_not_crash_on_fts5_special_characters(tmp_path):
    # Regression: "on-premise" (this project's own hosting vocabulary) used
    # to raise sqlite3.OperationalError -- FTS5's MATCH syntax treats "-" as
    # an exclusion operator, not literal text. An unbalanced quote raised a
    # separate "unterminated string" error.
    con = store.connect(tmp_path / "index.sqlite")
    store.index_documents(
        con,
        [
            {
                "kind": "source",
                "ref": "x",
                "line": 1,
                "title": "purchase approval",
                "snippet": "on-premise minimum amount",
                "version": "18.0",
            }
        ],
    )
    results = store.search(con, "on-premise")
    assert len(results) == 1
    assert store.search(con, '"unterminated') == []
    assert store.search(con, "") == []
    con.close()


def test_store_search_like_fallback_escapes_wildcards(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "has_fts5", lambda: False)
    con = store.connect(tmp_path / "index_like.sqlite")
    store.index_documents(
        con,
        [
            {
                "kind": "source",
                "ref": "x",
                "line": 1,
                "title": "test_case exact",
                "snippet": "literal underscore",
                "version": "18.0",
            },
            {
                "kind": "source",
                "ref": "y",
                "line": 1,
                "title": "testXcase should not match",
                "snippet": "an unescaped _ would wildcard-match this",
                "version": "18.0",
            },
        ],
    )
    results = store.search(con, "test_case")
    con.close()
    assert [r["title"] for r in results] == ["test_case exact"]


def test_store_clear_empties_the_table(tmp_path):
    con = store.connect(tmp_path / "index.sqlite")
    store.index_documents(con, _SAMPLE_DOCS)
    store.clear(con)
    results = store.search(con, "purchase")
    con.close()
    assert results == []


# -- search.py (end to end against the stub) -------------------------------------


def test_search_end_to_end_against_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKBOX_DATA_DIR", str(tmp_path / "data"))
    profile = Profile(
        odoo_version="18.0",
        edition="community",
        hosting="on-premise",
        odoo_source=str(STUB_18CE),
    )
    results = search_mod.search(profile, project_root=REPO_ROOT, query="purchase approval")
    assert results
    assert any("po_order_approval" in r["title"] for r in results)


def test_search_index_is_cached_across_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKBOX_DATA_DIR", str(tmp_path / "data"))
    profile = Profile(odoo_version="18.0", edition="community", odoo_source=str(STUB_18CE))
    path1 = search_mod.ensure_index(profile, project_root=REPO_ROOT)
    path2 = search_mod.ensure_index(profile, project_root=REPO_ROOT)
    assert path1 == path2
    assert path1.is_file()


def test_search_index_rebuilds_when_source_changes(tmp_path, monkeypatch):
    # Regression for a real bug hit while building P5's eval fixtures: a
    # settings view added *after* the first `checkbox search` call was
    # permanently invisible, silently, because the index only rebuilt when
    # the .sqlite file didn't exist yet at all.
    monkeypatch.setenv("CHECKBOX_DATA_DIR", str(tmp_path / "data"))
    addons = tmp_path / "addons"
    addon = addons / "demo"
    addon.mkdir(parents=True)
    (addon / "__manifest__.py").write_text("{'name': 'Demo'}\n", encoding="utf-8")
    # odoo_source resolves via find_addon_roots(), which expects an "addons"
    # child -- so it points at tmp_path, not tmp_path/addons.
    profile = Profile(odoo_version="18.0", edition="community", odoo_source=str(tmp_path))

    results = search_mod.search(profile, project_root=REPO_ROOT, query="tracking")
    assert results == []

    settings = addon / "res_config_settings.py"
    settings.write_text(
        "from odoo import fields, models\n"
        "class ResConfigSettings(models.TransientModel):\n"
        "    _inherit = 'res.config.settings'\n"
        "    x_tracking = fields.Boolean('Tracking')\n",
        encoding="utf-8",
    )
    results = search_mod.search(profile, project_root=REPO_ROOT, query="tracking")
    assert any("x_tracking" in r["title"] for r in results)


def test_search_kind_filter_excludes_other_kinds(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKBOX_DATA_DIR", str(tmp_path / "data"))
    profile = Profile(odoo_version="18.0", edition="community", odoo_source=str(STUB_18CE))
    results = search_mod.search(profile, project_root=REPO_ROOT, query="purchase", kinds=["docs"])
    assert results == []  # nothing of kind "docs" exists yet (P3 scope is source-only)


def test_search_does_not_rebuild_when_only_a_noise_dir_file_changes(tmp_path, monkeypatch):
    # The staleness check must stay in sync with what build() actually
    # reads: touching a file under i18n/ (never indexed) must not trigger
    # a reindex, or the noise-dir pruning in _newest_mtime would just move
    # the wasted work from "walk every call" to "reindex every call".
    monkeypatch.setenv("CHECKBOX_DATA_DIR", str(tmp_path / "data"))
    addons = tmp_path / "addons"
    addon = addons / "demo"
    (addon / "i18n").mkdir(parents=True)
    (addon / "__manifest__.py").write_text("{'name': 'Demo'}\n", encoding="utf-8")
    profile = Profile(odoo_version="18.0", edition="community", odoo_source=str(tmp_path))

    db_path = search_mod.ensure_index(profile, project_root=REPO_ROOT)
    first_mtime = db_path.stat().st_mtime

    import time

    time.sleep(0.01)
    (addon / "i18n" / "fr.po").write_text("# translation\n", encoding="utf-8")

    db_path_again = search_mod.ensure_index(profile, project_root=REPO_ROOT)
    assert db_path_again.stat().st_mtime == first_mtime  # not rebuilt
