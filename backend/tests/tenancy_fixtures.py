"""Shared test-tenancy constants (importable from any test module: pytest's
default rootdir import mode puts tests/ on sys.path).

conftest.py creates this organization once per test session, right after
truncating the isolated test schema, and the suite-wide auth override user
belongs to it. Tests that build root rows directly (Job, Candidate, ...)
set organization_id=TEST_ORG_ID.
"""
TEST_ORG_ID = 1
