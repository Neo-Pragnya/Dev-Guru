from shop.prices import price


class Cart:
    pass


def total(items):
    return sum(price(i) for i in items)
