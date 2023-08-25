# moshi-core

# Install
```
pip install moshi-core \
    -i https://us-central1-python.pkg.dev/moshi-3/pypi/simple
```

# Develop

## Setup
```
pyenv virtualenv 3.11.4 mc311 && \
    pyenv activate mc311 && \
    pip install -e .
```

## Test
`pytest -vsx --ff`

# Publish
`make publish`
