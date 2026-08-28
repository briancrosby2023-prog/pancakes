from operation_pancake.app import _page


def test_page_has_product_navigation():
    rendered = _page("Test", "<h1>Hello</h1>").decode()
    assert "Operation Pancake" in rendered
    assert 'href="/"' in rendered
    assert 'href="/compare"' in rendered
    assert "<h1>Hello</h1>" in rendered
