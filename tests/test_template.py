from simulator.template import TemplateRenderError, render_template


def test_render_template_success() -> None:
    rendered = render_template("https://{{HOST}}/{{DOMAIN}}", {"HOST": "example.com", "DOMAIN": "demo"})
    assert rendered == "https://example.com/demo"


def test_render_template_missing_key() -> None:
    try:
        render_template("{{MISSING}}", {})
    except TemplateRenderError as exc:
        assert "MISSING" in str(exc)
    else:
        raise AssertionError("TemplateRenderError was not raised")
