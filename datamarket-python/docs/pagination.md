# Pagination

Listings come back one page at a time. A page is a normal response model,
with the items in `data`, the position in `meta` and the cost in `usage`,
plus the means to fetch the pages after it.

## One page

```python
page = client.products.catalog(search="azeite", limit=50)

page.data  # the items of this page
page.meta.page  # 1
page.meta.pages  # 8
page.meta.total  # 376 items across every page
page.has_next  # True
len(page)  # 50
for product in page:  # iterates the items of this page only
    ...
```

Every page is billed when it is fetched, whether or not its items are used.

## The next page

```python
following = page.next_page()  # fetches page 2, billed; None on the last page
```

`next_page()` keeps the filters and page size of the call that produced the
first page.

## Walking pages

`iter_pages()` yields the page you already have, then fetches each following
page as the loop asks for it. It never requests the first page again.

```python
for current in page.iter_pages():
    print(current.meta.page, len(current))
```

`iter_all()` does the same and yields the items instead of the pages:

```python
for product in page.iter_all():
    print(product.ean, product.median_price)
```

Both stop when the API reports the last page or when a page comes back empty.

## Caps

Two keyword arguments bound a walk. They can be combined.

`max_pages` counts the pages requested beyond the one you already have, and
stops quietly:

```python
for product in page.iter_all(max_pages=2):  # this page plus two more at most
    ...
```

`max_units` caps what the walk may spend, measured by the real cost of each
page fetched. Before requesting a page, the SDK checks whether the estimated
cost of that page would cross the cap; if it would, it raises
`BudgetExceededError` after everything already paid for was yielded:

```python
from cnovatech.datamarket import errors

position = client.stores.market_position(store_id, limit=1000)  # 8 units per page
try:
    for item in position.iter_all(max_units=24):
        process(item)
except errors.BudgetExceededError as exc:
    print(exc.spent, "units spent,", exc.items_yielded, "items delivered")
```

The page you start from does not count against `max_units`: it was paid for
before the walk began.

To know the price of finishing before deciding:

```python
position.estimate_remaining_cost()  # pages after this one × estimated cost of a page
```

## Page size and cost

Each listing has its own maximum `limit`; the SDK refuses a larger value
before sending. For the exports, the cost of a page depends on `limit`: 250
rows cost the same as 1, so fetch pages as large as the endpoint allows when
you need everything, and small ones when you need a sample.

The catalogue has one more rule: beyond page 20 the API requires at least one
filter and answers `FilterRequiredError` otherwise. The SDK passes that error
through rather than working around it.

## Async

`AsyncDataMarket` returns `Async*` pages with the same members as coroutines
and asynchronous iterators:

```python
async with AsyncDataMarket() as client:
    page = await client.products.catalog(brand="COCA-COLA")
    following = await page.next_page()
    async for product in page.iter_all(max_pages=3):
        ...
```
