.PHONY: auth build cycle dev publish publish-nobump publish-nobump-nobuild precheck
# Source: https://web.mit.edu/gnu/doc/html/make_6.html

GOOGLE_CLOUD_PROJECT = moshi-3
GOOGLE_CLOUD_PYPI_URL = https://us-central1-python.pkg.dev/moshi-3/pypi/

auth:
	gcloud auth login

auth-install:
	PIP_NO_INPUT=1 pip install twine keyring keyrings.google-artifactregistry-auth

build-install:
	@echo "📦 Installing build tools..."
	PIP_NO_INPUT=1 pip install --upgrade pip
	PIP_NO_INPUT=1 pip install build twine
	@echo "📦✅ Installed."

build: auth-install build-install
	@echo "🏗 Building Python3 package..."
	rm -rf dist 2>/dev/null
	PIP_NO_INPUT=1 python -m build
	@echo "🏗✅ Built."

bump:
	@echo "📈 Bumping version..."
	./scripts/bump_version.sh
	@echo "📈✅ Bumped."

publish: bump publish-nobump

publish-nobump: build publish-nobump-nobuild

publish-nobump-nobuild:
	@echo "📤 Publishing to $(GOOGLE_CLOUD_PYPI_URL) ..."
	python3 -m twine upload \
		 --repository-url $(GOOGLE_CLOUD_PYPI_URL) \
		 "dist/*" \
		 --verbose
	@echo "📤✅ Published."

precheck:
	@python3 -c 'import sys; assert sys.version_info >= (3, 10), f"Python version >= 3.10 required, found {sys.version_info}"' \
        && echo "✅ Python 3 version >= 3.10" \
        || (echo "❌ Python 3 version < 3.10"; exit 1)
	@pip --version >/dev/null 2>&1 \
        && echo "✅ Pip installed" \
        || (echo "❌ Pip not found"; exit 1)
	@test -n "$GOOGLE_SDK_ROOT" \
        && echo "✅ GOOGLE_SDK_ROOT present in env" \
        || echo "❌ GOOGLE_SDK_ROOT missing in env"

test:
	@echo "🧪 Running tests..."
	pytest -v --cov=moshi
	@echo "🧪✅ Tests passed. Run `make test-cov` to view report."

test-cov: test
	@echo "📊 Showing test coverage report..."
	coverage report --format=total
	@echo "📊✅ Done."