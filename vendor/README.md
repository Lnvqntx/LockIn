# rumps 0.4.0 wheel

PyPI publishes rumps 0.4.0 as a source distribution. This directory includes a
pure-Python wheel built from the unmodified BSD-licensed release so that LockIn
can install with `uv pip install --only-binary :all: -r requirements.txt`.
The license is included in the wheel.

The upstream archive is
[rumps-0.4.0.tar.gz](https://files.pythonhosted.org/packages/b2/e2/2e6a47951290bd1a2831dcc50aec4b25d104c0cf00e8b7868cbd29cf3bfe/rumps-0.4.0.tar.gz).
Its SHA-256 digest is
`17fb33c21b54b1e25db0d71d1d793dc19dc3c0b7d8c79dc6d833d0cffc8b1596`.

To rebuild the wheel in a development environment, verify that digest and run
`uv build --wheel rumps-0.4.0.tar.gz --out-dir vendor` from the repository root.
Then run the Intel macOS dry run.

```sh
uv pip install --only-binary :all: --dry-run --python-platform x86_64-apple-darwin \
  --python-version 3.12 --target /tmp/lockin-wheel-check -r requirements.txt
```
