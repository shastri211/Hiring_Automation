"""GET /candidates/search - the manual-merge target picker."""
import uuid

from httpx import AsyncClient

from app.models.candidate import Candidate
from tenancy_fixtures import TEST_ORG_ID


async def test_search_matches_name_email_or_phone_and_skips_merged_and_excluded(client: AsyncClient, db_session):
    tag = uuid.uuid4().hex[:8]
    target = Candidate(organization_id=TEST_ORG_ID, canonical_name=f"Priya {tag}", primary_email=f"priya.{tag}@x.test")
    by_phone = Candidate(organization_id=TEST_ORG_ID, canonical_name="Other", primary_phone=f"555{tag}")
    self_row = Candidate(organization_id=TEST_ORG_ID, canonical_name=f"Priya {tag} (self)")
    db_session.add_all([target, by_phone, self_row])
    await db_session.flush()
    merged_away = Candidate(organization_id=TEST_ORG_ID, canonical_name=f"Priya {tag} old", merged_into_id=target.id)
    db_session.add(merged_away)
    await db_session.commit()

    res = await client.get("/candidates/search", params={"q": f"priya {tag}", "exclude_id": self_row.id})
    assert res.status_code == 200
    assert [c["id"] for c in res.json()] == [target.id]

    by_email = await client.get("/candidates/search", params={"q": f"PRIYA.{tag}@"})
    assert target.id in [c["id"] for c in by_email.json()]
    phone = await client.get("/candidates/search", params={"q": f"555{tag}"})
    assert [c["id"] for c in phone.json()] == [by_phone.id]


async def test_search_treats_like_wildcards_literally_and_requires_two_chars(client: AsyncClient):
    assert (await client.get("/candidates/search", params={"q": "%_"})).json() == []
    assert (await client.get("/candidates/search", params={"q": "a"})).status_code == 422
