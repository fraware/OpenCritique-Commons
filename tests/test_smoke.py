from fastapi import FastAPI


def test_public_packages_import() -> None:
    import opencritique_acquisition
    import opencritique_adapters
    import opencritique_evaluation
    import opencritique_registry
    import opencritique_schema

    assert opencritique_acquisition is not None
    assert opencritique_adapters is not None
    assert opencritique_evaluation is not None
    assert opencritique_registry is not None
    assert opencritique_schema is not None


def test_registry_application_is_fastapi() -> None:
    from opencritique_registry.api import app

    assert isinstance(app, FastAPI)


def test_core_models_are_exported() -> None:
    from opencritique_schema.models import Concern, EvidenceItem, RunManifest

    assert Concern.__name__ == 'Concern'
    assert EvidenceItem.__name__ == 'EvidenceItem'
    assert RunManifest.__name__ == 'RunManifest'
