from datetime import UTC, datetime
from decimal import Decimal
from copy import deepcopy
from uuid import uuid4

from domain.listings.models import Listing, ListingStatus, ItemCondition
from domain.search.models import SearchQuery
from domain.search.service import SearchService


def make_listing(title, desc, category, cond, price, loc, status, created_offset=0):
    return Listing(
        id=uuid4(),
        seller_id=uuid4(),
        title=title,
        description=desc,
        category=category,
        condition=cond,
        price=Decimal(price),
        currency="USD",
        location=loc,
        status=status,
        created_at=datetime.now(UTC),
    )


def test_keyword_matches_title_or_description():
    s = SearchService()
    l1 = make_listing("Red Bike", "Fast bike", "bikes", ItemCondition.GOOD, "10", "Town", ListingStatus.PUBLISHED)
    l2 = make_listing("Blue Car", "Red convertible", "cars", ItemCondition.GOOD, "100", "Town", ListingStatus.PUBLISHED)
    res = s.search([l1, l2], SearchQuery(keyword="red"))
    assert l1 in res
    assert l2 in res


def test_category_filters():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.GOOD, "10", "Town", ListingStatus.PUBLISHED)
    l2 = make_listing("B", "", "cars", ItemCondition.GOOD, "10", "Town", ListingStatus.PUBLISHED)
    res = s.search([l1, l2], SearchQuery(category="bikes"))
    assert res == (l1,)


def test_condition_filters():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.PUBLISHED)
    l2 = make_listing("B", "", "bikes", ItemCondition.GOOD, "10", "Town", ListingStatus.PUBLISHED)
    res = s.search([l1, l2], SearchQuery(condition=ItemCondition.NEW))
    assert res == (l1,)


def test_location_case_insensitive():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "NewTown", ListingStatus.PUBLISHED)
    res = s.search([l1], SearchQuery(location="newtown"))
    assert res == (l1,)


def test_price_range_inclusive():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.PUBLISHED)
    l2 = make_listing("B", "", "bikes", ItemCondition.NEW, "20", "Town", ListingStatus.PUBLISHED)
    res = s.search([l1, l2], SearchQuery(min_price=Decimal("10"), max_price=Decimal("20")))
    assert {r.id for r in res} == {l1.id, l2.id}


def test_unpublished_hidden():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.DRAFT)
    res = s.search([l1], SearchQuery())
    assert res == ()


def test_newest_first():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.PUBLISHED)
    l2 = make_listing("B", "", "bikes", ItemCondition.NEW, "20", "Town", ListingStatus.PUBLISHED)
    # adjust created_at so l2 is newer
    l1 = Listing(**{**l1.__dict__, "created_at": datetime(2020, 1, 1, tzinfo=UTC)})
    l2 = Listing(**{**l2.__dict__, "created_at": datetime(2021, 1, 1, tzinfo=UTC)})
    res = s.search([l1, l2], SearchQuery())
    assert res == (l2, l1)


def test_empty_results_and_input_unchanged():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.PUBLISHED)
    original = deepcopy([l1])
    res = s.search([l1], SearchQuery(keyword="nomatch"))
    assert res == ()
    assert original == [l1]


def test_invalid_price_range_raises():
    s = SearchService()
    l1 = make_listing("A", "", "bikes", ItemCondition.NEW, "10", "Town", ListingStatus.PUBLISHED)
    try:
        s.search([l1], SearchQuery(min_price=Decimal("20"), max_price=Decimal("10")))
        assert False, "expected ValueError"
    except ValueError:
        pass
