import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_site import index_html, site_name
from validate_workspaces import REPO


def test_site_name_joins_path_parts():
    assert site_name(REPO, REPO / "examples" / "shop" / "workspace.dsl") == "examples-shop"


def test_index_links_every_site():
    page = index_html(["examples-shop", "workspaces-core"])
    assert 'href="examples-shop/"' in page
    assert 'href="workspaces-core/"' in page
