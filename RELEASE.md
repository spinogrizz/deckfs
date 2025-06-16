# Release Process

This document describes how to release a new version of deckfs.

## Automated Release via GitHub Actions

The project uses GitHub Actions to automatically build and publish releases when a new version tag is pushed.

### Steps to create a new release:

1. **Update version locally** (optional, will be done automatically):
   ```bash
   # Version will be automatically extracted from git tag
   # But you can update pyproject.toml manually if needed
   ```

2. **Create and push a version tag**:
   ```bash
   # Create a new tag with version (e.g., v0.1.1)
   git tag v0.1.1
   
   # Push the tag to trigger the release workflow
   git push origin v0.1.1
   ```

3. **Monitor the GitHub Actions workflow**:
   - Go to the Actions tab in your GitHub repository
   - Watch the "Build and Publish to PyPI" workflow
   - It will automatically:
     - Extract version from the tag
     - Update `pyproject.toml` with the version
     - Build wheel and source distribution
     - Verify package contents
     - Publish to PyPI (using trusted publishing)
     - Create a GitHub release with artifacts

## What the workflow does:

1. **Triggers on**: Git tags matching `v*` pattern (e.g., `v0.1.1`, `v1.0.0`)
2. **Builds**: Both wheel (`.whl`) and source distribution (`.tar.gz`)
3. **Publishes to**: PyPI using trusted publishing (no API tokens needed)
4. **Creates**: GitHub release with downloadable artifacts
5. **Includes**: Config.yaml.example and all dependencies properly declared

## Prerequisites

### For PyPI Publishing (Trusted Publishing)

1. **Configure trusted publishing on PyPI**:
   - Go to your PyPI project settings
   - Add GitHub as a trusted publisher
   - Set repository: `spinogrizz/deckfs` (or your actual repository path)
   - Set workflow filename: `release.yml`
   - Set environment name: `release` (must match workflow environment)
   
2. **Create GitHub Environment**:
   - Go to repository Settings → Environments
   - Create new environment named `release`
   - Optionally add protection rules (reviewers, branch restrictions)

### Alternative: Using API Tokens

If you prefer API tokens instead of trusted publishing:

1. Generate PyPI API token
2. Add it as `PYPI_API_TOKEN` in GitHub repository secrets
3. Update the workflow to use token-based authentication:
   ```yaml
   - name: Publish to PyPI
     env:
       TWINE_USERNAME: __token__
       TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
     run: twine upload dist/*
   ```

## Version Numbering

Follow semantic versioning (semver):
- `v0.1.0` - Initial release
- `v0.1.1` - Patch release (bug fixes)
- `v0.2.0` - Minor release (new features, backwards compatible)  
- `v1.0.0` - Major release (breaking changes)

## Testing a Release

Before creating a real release, you can test locally:

```bash
# Build the package
python -m build

# Check the package
python -m twine check dist/*

# Test install locally
pip install dist/*.whl

# Test the installation
deckfs --version
```

## Manual Release (if needed)

If you need to release manually:

```bash
# Clean previous builds
rm -rf dist/ build/

# Update version in pyproject.toml manually
# version = "0.1.1"

# Build the package
python -m build

# Upload to PyPI
python -m twine upload dist/*

# Create git tag
git tag v0.1.1
git push origin v0.1.1
```