# Fixture policy

Memory sessions can resemble private account and trading history even when
synthetic. Tests therefore generate event streams and order lifecycles inside
pytest-provided temporary directories instead of publishing runtime-like JSONL
or order-record artifacts.

`tests/test_memory.py` covers a read-only event stream, a normalized synthetic
snapshot, and complete legal/illegal order transitions without network,
brokerage, authentication, consent, or live account data.
