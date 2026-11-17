from tools.check_docs import find_documentation_issues


def test_required_documentation_navigation_is_complete() -> None:
    assert find_documentation_issues() == []
