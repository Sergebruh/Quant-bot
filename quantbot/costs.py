"""Trading costs: commissions and slippage."""


def commission(shares, per_share, minimum):
    """Commission in dollars for one order of `shares` (any sign)."""
    shares = abs(shares)
    if shares == 0:
        return 0.0
    return max(shares * per_share, minimum)


def fill_price(price, side, slippage_bps):
    """Price actually paid/received. side=+1 buy (pay more), -1 sell (get less)."""
    return price * (1 + side * slippage_bps / 10_000)
