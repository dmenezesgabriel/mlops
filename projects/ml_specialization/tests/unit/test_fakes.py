import pytest
from fakes import import_module_for


def test_import_module_for_rejects_unmapped_name() -> None:
    # Arrange — an import outside the declared mapping is a wiring error.
    import_module = import_module_for({"mlflow": object()})

    # Act / Assert
    with pytest.raises(ImportError, match="Unexpected import other"):
        import_module("other")
