from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
REQUIREMENTS = ROOT / "requirements.txt"
ENTRY = ROOT / "app" / "entry.py"


def test_production_image_uses_composed_object_entrypoint() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "OBJECT_API_ENABLED=true" in dockerfile
    assert '"app.entry:app"' in dockerfile
    assert '"app.main:app"' not in dockerfile


def test_object_runtime_dependency_and_lifespan_are_present() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    entry = ENTRY.read_text(encoding="utf-8")

    assert "boto3>=" in requirements
    assert "ObjectRegistry(" in entry
    assert "S3ObjectStore(object_settings)" in entry
    assert "build_object_router(" in entry
    assert "_base_lifespan(application)" in entry
