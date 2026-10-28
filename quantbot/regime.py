"""Hidden Markov Model regime filter: is the market trending intraday?

Each day is summarized by features known at that day's close:
  - vr: variance ratio, var(30-min returns) / (6 x var(5-min returns)). Above
    1 means moves within the day tend to continue (trending); below 1 means
    they tend to reverse (choppy).
  - vr5: 5-day average of vr (less noisy). The default feature.
  - log_rv: log realized volatility of 5-minute returns. Not used by default:
    with it, the HMM's states mostly track volatility instead of trendiness.
The first feature listed must be the trendiness one.

A Gaussian HMM learns hidden states from these. It is refit every
`refit_every` days on a rolling window of past days only. The probability of
each state for day t uses only data up to day t-1: the FILTERED probability at
t-1 (forward algorithm) pushed one step through the transition matrix. The
Viterbi path and smoothed probabilities are never used, because they look at
the future.
"""

import warnings

import numpy as np
import pandas as pd
from scipy.special import logsumexp

from .intraday import session_dates


def daily_features(bars):
    """DataFrame indexed by date with columns vr and log_rv."""
    day = session_dates(bars.index).to_numpy()

    def one_day(g):
        x = np.log(g["close"].to_numpy())
        r1 = np.diff(x)
        r6 = x[6:] - x[:-6]
        v1 = np.var(r1) if len(r1) > 12 else np.nan
        vr = np.var(r6) / (6 * v1) if v1 and v1 > 0 else np.nan
        rv = np.sqrt(np.sum(r1**2)) if len(r1) else np.nan
        return pd.Series({"vr": vr, "log_rv": np.log(rv) if rv and rv > 0 else np.nan})

    feats = bars.groupby(day).apply(one_day)
    # Smoothed trendiness: daily variance ratios are very noisy on their own.
    feats["vr5"] = feats["vr"].rolling(5).mean()
    return feats


def _forward_filter(model, X):
    """Filtered state probabilities P(state_t | x_1..x_t) for each row of X."""
    log_b = model._compute_log_likelihood(X)
    log_a = np.log(model.transmat_ + 1e-300)
    alpha = np.log(model.startprob_ + 1e-300) + log_b[0]
    out = np.empty_like(log_b)
    out[0] = alpha - logsumexp(alpha)
    for t in range(1, len(X)):
        alpha = logsumexp(out[t - 1][:, None] + log_a, axis=0) + log_b[t]
        out[t] = alpha - logsumexp(alpha)
    return np.exp(out)


_CACHE = {}


def trend_probability(bars, n_states=2, train_days=756, min_train_days=252,
                      refit_every=21, seed=0, features=("vr5",)):
    features = tuple(features)
    key = (len(bars), bars.index[0], bars.index[-1], n_states, train_days,
           min_train_days, refit_every, seed, features)
    if key not in _CACHE:
        _CACHE[key] = _trend_probability(bars, n_states, train_days, min_train_days,
                                         refit_every, seed, features)
    return _CACHE[key]


def _trend_probability(bars, n_states, train_days, min_train_days, refit_every, seed,
                       features):
    """Per-day probability (known before the open) that today is 'trending'.

    The trending state is the one with the highest average variance ratio.
    Returns a Series indexed by date; NaN until enough history exists.
    """
    from hmmlearn.hmm import GaussianHMM

    feats = daily_features(bars)[list(features)].dropna()
    X_all = feats.to_numpy()
    dates = feats.index
    prob = pd.Series(np.nan, index=dates)

    for block_start in range(min_train_days, len(dates), refit_every):
        lo = max(0, block_start - train_days)
        X_train = X_all[lo:block_start]
        mu, sd = X_train.mean(axis=0), X_train.std(axis=0)
        model = GaussianHMM(n_components=n_states, covariance_type="full",
                            n_iter=200, random_state=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit((X_train - mu) / sd)
        trending = int(np.argmax(model.means_[:, 0]))  # first feature = trendiness

        block_end = min(block_start + refit_every, len(dates))
        # Filter through the training window and this block, with frozen params.
        filt = _forward_filter(model, (X_all[lo:block_end] - mu) / sd)
        predicted = filt @ model.transmat_     # row t: P(state at t+1 | data to t)
        for t in range(block_start, block_end):
            prob.iloc[t] = predicted[t - lo - 1, trending]
    return prob


def regime_scale(bars, cfg):
    """Per-bar multiplier from the regime filter (1 = trade, 0 = skip)."""
    r = cfg["regime"]
    prob = trend_probability(bars, r["n_states"], r["train_window"],
                             r["min_train_days"], r["refit_every"],
                             features=r.get("features", ["vr5"]))
    day = session_dates(bars.index)
    p = day.map(prob).astype(float)
    if r["mode"] == "filter":
        return (p > r["trend_prob_threshold"]).astype(float).where(p.notna())
    if r["mode"] == "scale":
        return p
    raise ValueError(f"unknown regime mode {r['mode']!r}")
