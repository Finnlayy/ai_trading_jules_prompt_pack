"""
Pattern Recognition Engine — classical chart pattern detection using pure NumPy.

Detects:
- Head and Shoulders (bullish / bearish / inverse)
- Double Top / Double Bottom
- Flags and Pennants
- Ascending / Descending / Symmetric Triangles
- Rising / Falling Wedges

All functions are stateless and operate on OHLCV arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class PatternMatch:
    pattern_type: str
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confidence: float  # 0.0–1.0
    start_idx: int
    end_idx: int
    neckline: float | None = None
    target_price: float | None = None


# ---------------------------------------------------------------------------
# Local extrema
# ---------------------------------------------------------------------------

def _local_extrema(
    highs: np.ndarray, lows: np.ndarray, order: int = 5
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Find local maxima in *highs* and local minima in *lows* using a sliding
    window of `order` bars on each side.

    Returns:
        (peak_indices, trough_indices)
    """
    n = len(highs)
    peaks: List[int] = []
    troughs: List[int] = []
    for i in range(order, n - order):
        if highs[i] == np.max(highs[i - order : i + order + 1]):
            peaks.append(i)
        if lows[i] == np.min(lows[i - order : i + order + 1]):
            troughs.append(i)
    return np.array(peaks), np.array(troughs)


# ---------------------------------------------------------------------------
# Head and Shoulders
# ---------------------------------------------------------------------------

def detect_head_and_shoulders(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, order: int = 5
) -> PatternMatch | None:
    """
    Detect classic Head-and-Shoulders (bearish reversal) and
    Inverse Head-and-Shoulders (bullish reversal).
    """
    peaks, troughs = _local_extrema(highs, lows, order)
    if len(peaks) < 3 or len(troughs) < 2:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    for i in range(len(peaks) - 2):
        ls_idx = peaks[i]
        h_idx = peaks[i + 1]
        rs_idx = peaks[i + 2]

        # Head must be the highest
        if not (highs[h_idx] > highs[ls_idx] and highs[h_idx] > highs[rs_idx]):
            continue

        # Shoulders should be roughly equal (±15% of head height)
        head_height = highs[h_idx] - min(lows[ls_idx], lows[rs_idx])
        shoulder_diff = abs(highs[ls_idx] - highs[rs_idx])
        if head_height <= 0 or shoulder_diff / head_height > 0.30:
            continue

        # Find neckline troughs between LS-H and H-RS
        t1_candidates = troughs[(troughs > ls_idx) & (troughs < h_idx)]
        t2_candidates = troughs[(troughs > h_idx) & (troughs < rs_idx)]
        if len(t1_candidates) == 0 or len(t2_candidates) == 0:
            continue

        t1_idx = t1_candidates[np.argmin(lows[t1_candidates])]
        t2_idx = t2_candidates[np.argmin(lows[t2_candidates])]
        neckline = (lows[t1_idx] + lows[t2_idx]) / 2.0

        # Symmetry check: distance LS-H roughly equals H-RS (±30%)
        dist_ls_h = h_idx - ls_idx
        dist_h_rs = rs_idx - h_idx
        if dist_ls_h <= 0 or abs(dist_ls_h - dist_h_rs) / max(dist_ls_h, dist_h_rs) > 0.40:
            continue

        # Breakout confirmation: price below neckline after RS
        if rs_idx + 1 < len(closes):
            confirm = np.any(closes[rs_idx + 1 : min(rs_idx + order * 2, len(closes))] < neckline)
        else:
            confirm = False

        # Confidence scoring
        symmetry_score = 1.0 - abs(dist_ls_h - dist_h_rs) / max(dist_ls_h, dist_h_rs)
        shoulder_score = 1.0 - shoulder_diff / head_height
        breakout_score = 1.0 if confirm else 0.5
        confidence = min(1.0, (symmetry_score * 0.35 + shoulder_score * 0.35 + breakout_score * 0.30))

        if confidence > best_score:
            best_score = confidence
            target = neckline - (highs[h_idx] - neckline)
            best = PatternMatch(
                pattern_type="HEAD_AND_SHOULDERS",
                direction="SHORT",
                confidence=confidence,
                start_idx=ls_idx,
                end_idx=rs_idx + order * 2 if rs_idx + order * 2 < len(closes) else rs_idx,
                neckline=round(neckline, 4),
                target_price=round(target, 4),
            )

    # Inverse H&S (bullish) — scan troughs
    if len(troughs) >= 3 and len(peaks) >= 2:
        for i in range(len(troughs) - 2):
            ls_idx = troughs[i]
            h_idx = troughs[i + 1]
            rs_idx = troughs[i + 2]

            if not (lows[h_idx] < lows[ls_idx] and lows[h_idx] < lows[rs_idx]):
                continue

            head_depth = max(highs[ls_idx], highs[rs_idx]) - lows[h_idx]
            shoulder_diff = abs(lows[ls_idx] - lows[rs_idx])
            if head_depth <= 0 or shoulder_diff / head_depth > 0.30:
                continue

            p1_candidates = peaks[(peaks > ls_idx) & (peaks < h_idx)]
            p2_candidates = peaks[(peaks > h_idx) & (peaks < rs_idx)]
            if len(p1_candidates) == 0 or len(p2_candidates) == 0:
                continue

            p1_idx = p1_candidates[np.argmax(highs[p1_candidates])]
            p2_idx = p2_candidates[np.argmax(highs[p2_candidates])]
            neckline = (highs[p1_idx] + highs[p2_idx]) / 2.0

            dist_ls_h = h_idx - ls_idx
            dist_h_rs = rs_idx - h_idx
            if dist_ls_h <= 0 or abs(dist_ls_h - dist_h_rs) / max(dist_ls_h, dist_h_rs) > 0.40:
                continue

            if rs_idx + 1 < len(closes):
                confirm = np.any(closes[rs_idx + 1 : min(rs_idx + order * 2, len(closes))] > neckline)
            else:
                confirm = False

            symmetry_score = 1.0 - abs(dist_ls_h - dist_h_rs) / max(dist_ls_h, dist_h_rs)
            shoulder_score = 1.0 - shoulder_diff / head_depth
            breakout_score = 1.0 if confirm else 0.5
            confidence = min(1.0, (symmetry_score * 0.35 + shoulder_score * 0.35 + breakout_score * 0.30))

            if confidence > best_score:
                best_score = confidence
                target = neckline + (neckline - lows[h_idx])
                best = PatternMatch(
                    pattern_type="INVERSE_HEAD_AND_SHOULDERS",
                    direction="LONG",
                    confidence=confidence,
                    start_idx=ls_idx,
                    end_idx=rs_idx + order * 2 if rs_idx + order * 2 < len(closes) else rs_idx,
                    neckline=round(neckline, 4),
                    target_price=round(target, 4),
                )

    return best


# ---------------------------------------------------------------------------
# Double Top / Double Bottom
# ---------------------------------------------------------------------------

def detect_double_top(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, order: int = 5
) -> PatternMatch | None:
    """Bearish reversal pattern."""
    peaks, troughs = _local_extrema(highs, lows, order)
    if len(peaks) < 2 or len(troughs) < 1:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    for i in range(len(peaks) - 1):
        p1 = peaks[i]
        p2 = peaks[i + 1]
        distance = p2 - p1
        if distance < 5 or distance > 60:
            continue

        # Peaks should be roughly equal (±5%)
        peak_diff = abs(highs[p1] - highs[p2]) / ((highs[p1] + highs[p2]) / 2.0)
        if peak_diff > 0.05:
            continue

        # Trough between the peaks
        t_candidates = troughs[(troughs > p1) & (troughs < p2)]
        if len(t_candidates) == 0:
            continue
        t_idx = t_candidates[np.argmin(lows[t_candidates])]
        neckline = lows[t_idx]

        # Breakout below neckline after second peak
        if p2 + 1 >= len(closes):
            continue
        confirm = np.any(closes[p2 + 1 : min(p2 + order * 2, len(closes))] < neckline)

        confidence = min(1.0, 1.0 - peak_diff * 10) * (1.0 if confirm else 0.6)
        if confidence > best_score:
            best_score = confidence
            best = PatternMatch(
                pattern_type="DOUBLE_TOP",
                direction="SHORT",
                confidence=confidence,
                start_idx=p1,
                end_idx=p2 + order * 2 if p2 + order * 2 < len(closes) else p2,
                neckline=round(neckline, 4),
                target_price=round(neckline - (highs[p1] - neckline), 4),
            )

    return best


def detect_double_bottom(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, order: int = 5
) -> PatternMatch | None:
    """Bullish reversal pattern."""
    peaks, troughs = _local_extrema(highs, lows, order)
    if len(troughs) < 2 or len(peaks) < 1:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    for i in range(len(troughs) - 1):
        t1 = troughs[i]
        t2 = troughs[i + 1]
        distance = t2 - t1
        if distance < 5 or distance > 60:
            continue

        trough_diff = abs(lows[t1] - lows[t2]) / ((lows[t1] + lows[t2]) / 2.0)
        if trough_diff > 0.05:
            continue

        p_candidates = peaks[(peaks > t1) & (peaks < t2)]
        if len(p_candidates) == 0:
            continue
        p_idx = p_candidates[np.argmax(highs[p_candidates])]
        neckline = highs[p_idx]

        if t2 + 1 >= len(closes):
            continue
        confirm = np.any(closes[t2 + 1 : min(t2 + order * 2, len(closes))] > neckline)

        confidence = min(1.0, 1.0 - trough_diff * 10) * (1.0 if confirm else 0.6)
        if confidence > best_score:
            best_score = confidence
            best = PatternMatch(
                pattern_type="DOUBLE_BOTTOM",
                direction="LONG",
                confidence=confidence,
                start_idx=t1,
                end_idx=t2 + order * 2 if t2 + order * 2 < len(closes) else t2,
                neckline=round(neckline, 4),
                target_price=round(neckline + (neckline - lows[t1]), 4),
            )

    return best


# ---------------------------------------------------------------------------
# Flags and Pennants
# ---------------------------------------------------------------------------

def detect_flag(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray | None = None,
    order: int = 3,
) -> PatternMatch | None:
    """
    Detect bull / bear flags and pennants.
    Requires a strong trend (pole) followed by a small consolidation.
    """
    n = len(closes)
    if n < 20:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    for start in range(0, n - 20):
        # Pole: strong move over ~5-15 bars
        pole_end = min(start + 15, n - 5)
        pole = closes[start:pole_end]
        pole_change = (pole[-1] - pole[0]) / pole[0] if pole[0] != 0 else 0
        pole_strength = abs(pole_change)
        if pole_strength < 0.03:  # Need at least 3% move
            continue

        trend_direction = "LONG" if pole_change > 0 else "SHORT"

        # Consolidation: next 3-10 bars
        for cons_len in range(3, 11):
            cons_start = pole_end
            cons_end = cons_start + cons_len
            if cons_end >= n:
                break

            cons_highs = highs[cons_start:cons_end]
            cons_lows = lows[cons_start:cons_end]
            cons_closes = closes[cons_start:cons_end]

            # Flag: parallel channel against trend
            # Pennant: converging triangle
            max_h = np.max(cons_highs)
            min_l = np.min(cons_lows)
            range_pct = (max_h - min_l) / ((max_h + min_l) / 2.0)

            if range_pct > 0.02:  # Too volatile for flag/pennant
                continue

            # Check for breakout in trend direction after consolidation
            after = cons_end
            if after >= n:
                continue
            breakout_confirmed = False
            if trend_direction == "LONG" and closes[after] > max_h:
                breakout_confirmed = True
            if trend_direction == "SHORT" and closes[after] < min_l:
                breakout_confirmed = True

            # Volume decline during consolidation (optional)
            vol_score = 0.5
            if volumes is not None and cons_start > 0:
                pole_vol = np.mean(volumes[start:cons_start])
                cons_vol = np.mean(volumes[cons_start:cons_end])
                if pole_vol > 0 and cons_vol < pole_vol * 0.8:
                    vol_score = 1.0

            confidence = min(1.0, pole_strength / 0.10 * 0.4 + vol_score * 0.3 + (0.3 if breakout_confirmed else 0.15))

            if confidence > best_score:
                best_score = confidence
                pattern_type = "BULL_FLAG" if trend_direction == "LONG" else "BEAR_FLAG"
                # Simple target: pole height projected from breakout
                target = closes[after] + (closes[pole_end - 1] - closes[start]) if trend_direction == "LONG" else closes[after] - (closes[start] - closes[pole_end - 1])
                best = PatternMatch(
                    pattern_type=pattern_type,
                    direction=trend_direction,
                    confidence=confidence,
                    start_idx=start,
                    end_idx=after,
                    target_price=round(target, 4),
                )

    return best


# ---------------------------------------------------------------------------
# Triangles
# ---------------------------------------------------------------------------

def detect_triangle(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, min_touches: int = 2
) -> PatternMatch | None:
    """
    Detect ascending, descending, and symmetric triangles.
    Looks for converging trendlines with at least `min_touches` on each side.
    """
    n = len(closes)
    if n < 20:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    # Use local extrema with small order to catch more touches
    peaks, troughs = _local_extrema(highs, lows, order=2)
    if len(peaks) < min_touches + 1 or len(troughs) < min_touches + 1:
        return None

    # Try various window sizes
    for window_start in range(0, n - 20):
        window_end = min(window_start + 40, n)
        w_peaks = peaks[(peaks >= window_start) & (peaks < window_end)]
        w_troughs = troughs[(troughs >= window_start) & (troughs < window_end)]

        if len(w_peaks) < min_touches or len(w_troughs) < min_touches:
            continue

        # Fit upper trendline through peaks (descending: negative slope)
        if len(w_peaks) >= min_touches:
            x_up = w_peaks.astype(float)
            y_up = highs[w_peaks]
            slope_up, intercept_up = np.polyfit(x_up, y_up, 1)
        else:
            continue

        # Fit lower trendline through troughs (ascending: positive slope)
        x_lo = w_troughs.astype(float)
        y_lo = lows[w_troughs]
        slope_lo, intercept_lo = np.polyfit(x_lo, y_lo, 1)

        # Triangles require convergence (slopes with opposite signs or one flat)
        if slope_up >= 0 or slope_lo <= 0:
            continue

        # Check touches
        up_touches = np.sum(np.abs(highs[w_peaks] - (slope_up * w_peaks + intercept_up)) < (np.max(highs) - np.min(lows)) * 0.02)
        lo_touches = np.sum(np.abs(lows[w_troughs] - (slope_lo * w_troughs + intercept_lo)) < (np.max(highs) - np.min(lows)) * 0.02)

        if up_touches < min_touches or lo_touches < min_touches:
            continue

        # Apex (where lines cross)
        if abs(slope_up - slope_lo) < 1e-9:
            continue
        apex_x = (intercept_lo - intercept_up) / (slope_up - slope_lo)
        if apex_x < window_end or apex_x > window_end + 20:
            continue

        # Breakout detection
        last_idx = window_end - 1
        upper_at_last = slope_up * last_idx + intercept_up
        lower_at_last = slope_lo * last_idx + intercept_lo
        mid = (upper_at_last + lower_at_last) / 2.0

        direction = "NEUTRAL"
        confirm = False
        if last_idx + 1 < n:
            if closes[last_idx + 1] > upper_at_last:
                direction = "LONG"
                confirm = True
            elif closes[last_idx + 1] < lower_at_last:
                direction = "SHORT"
                confirm = True

        # Triangle type classification
        if slope_up < -0.001 and slope_lo > 0.001:
            triangle_type = "SYMMETRIC_TRIANGLE"
        elif abs(slope_up) < 0.001 and slope_lo > 0.001:
            triangle_type = "ASCENDING_TRIANGLE"
        elif slope_up < -0.001 and abs(slope_lo) < 0.001:
            triangle_type = "DESCENDING_TRIANGLE"
        else:
            triangle_type = "TRIANGLE"

        convergence = min(1.0, abs(slope_up - slope_lo) * 50)
        touch_score = min(1.0, (up_touches + lo_touches) / 6.0)
        breakout_score = 1.0 if confirm else 0.4
        confidence = min(1.0, convergence * 0.3 + touch_score * 0.4 + breakout_score * 0.3)

        if confidence > best_score:
            best_score = confidence
            best = PatternMatch(
                pattern_type=triangle_type,
                direction=direction,
                confidence=confidence,
                start_idx=window_start,
                end_idx=last_idx,
                neckline=round(mid, 4),
            )

    return best


# ---------------------------------------------------------------------------
# Wedges
# ---------------------------------------------------------------------------

def detect_wedge(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray
) -> PatternMatch | None:
    """
    Detect rising wedge (bearish) and falling wedge (bullish).
    Both trendlines point in the same direction but converge.
    """
    n = len(closes)
    if n < 20:
        return None

    best: PatternMatch | None = None
    best_score = 0.0

    peaks, troughs = _local_extrema(highs, lows, order=2)
    if len(peaks) < 3 or len(troughs) < 3:
        return None

    for window_start in range(0, n - 20):
        window_end = min(window_start + 40, n)
        w_peaks = peaks[(peaks >= window_start) & (peaks < window_end)]
        w_troughs = troughs[(troughs >= window_start) & (troughs < window_end)]

        if len(w_peaks) < 3 or len(w_troughs) < 3:
            continue

        x_up = w_peaks.astype(float)
        y_up = highs[w_peaks]
        slope_up, intercept_up = np.polyfit(x_up, y_up, 1)

        x_lo = w_troughs.astype(float)
        y_lo = lows[w_troughs]
        slope_lo, intercept_lo = np.polyfit(x_lo, y_lo, 1)

        # Wedges: same direction slopes, converging
        both_rising = slope_up > 0.001 and slope_lo > 0.001 and slope_up > slope_lo
        both_falling = slope_up < -0.001 and slope_lo < -0.001 and slope_up < slope_lo

        if not (both_rising or both_falling):
            continue

        # Check touches
        up_touches = np.sum(np.abs(highs[w_peaks] - (slope_up * w_peaks + intercept_up)) < (np.max(highs) - np.min(lows)) * 0.02)
        lo_touches = np.sum(np.abs(lows[w_troughs] - (slope_lo * w_troughs + intercept_lo)) < (np.max(highs) - np.min(lows)) * 0.02)

        if up_touches < 2 or lo_touches < 2:
            continue

        last_idx = window_end - 1
        upper_at_last = slope_up * last_idx + intercept_up
        lower_at_last = slope_lo * last_idx + intercept_lo

        direction = "SHORT" if both_rising else "LONG"
        pattern_type = "RISING_WEDGE" if both_rising else "FALLING_WEDGE"

        confirm = False
        if last_idx + 1 < n:
            if both_rising and closes[last_idx + 1] < lower_at_last:
                confirm = True
            if both_falling and closes[last_idx + 1] > upper_at_last:
                confirm = True

        convergence = min(1.0, abs(slope_up - slope_lo) * 100)
        touch_score = min(1.0, (up_touches + lo_touches) / 6.0)
        breakout_score = 1.0 if confirm else 0.4
        confidence = min(1.0, convergence * 0.3 + touch_score * 0.4 + breakout_score * 0.3)

        if confidence > best_score:
            best_score = confidence
            best = PatternMatch(
                pattern_type=pattern_type,
                direction=direction,
                confidence=confidence,
                start_idx=window_start,
                end_idx=last_idx,
                neckline=round((upper_at_last + lower_at_last) / 2.0, 4),
            )

    return best


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def scan_patterns(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray | None = None,
) -> List[PatternMatch]:
    """
    Run all pattern detectors and return a list of detected patterns.
    Only returns patterns with confidence >= 0.4.
    """
    results: List[PatternMatch] = []
    detectors = [
        detect_head_and_shoulders,
        detect_double_top,
        detect_double_bottom,
        detect_flag,
        detect_triangle,
        detect_wedge,
    ]
    for detector in detectors:
        try:
            if detector.__name__ == "detect_flag":
                match = detector(closes, highs, lows, volumes)
            else:
                match = detector(closes, highs, lows)
            if match is not None and match.confidence >= 0.4:
                results.append(match)
        except Exception:
            # Individual detectors may fail on edge-case data; fail open
            continue
    return results


def aggregate_pattern_score(
    matches: Sequence[PatternMatch],
) -> Tuple[float, str | None, float]:
    """
    Aggregate multiple pattern matches into a single score.

    Returns:
        (pattern_score 0-100, dominant_pattern_type or None, avg_confidence 0-1)
    """
    if not matches:
        return 0.0, None, 0.0

    # Weight by confidence
    total_weight = sum(m.confidence for m in matches)
    if total_weight == 0:
        return 0.0, None, 0.0

    avg_confidence = total_weight / len(matches)
    # Scale to 0-100
    pattern_score = min(100.0, avg_confidence * 100)

    # Dominant pattern = highest confidence
    dominant = max(matches, key=lambda m: m.confidence)

    return round(pattern_score, 2), dominant.pattern_type, round(avg_confidence, 3)


# ---------------------------------------------------------------------------
# Candle adapter
# ---------------------------------------------------------------------------

def scan_bars(bars: Sequence) -> List[PatternMatch]:
    """
    Adapter that takes a sequence of candle-like objects (with .c, .h, .l, .v)
    and runs pattern detection.
    """
    if len(bars) < 20:
        return []

    closes = np.array([b.c for b in bars])
    highs = np.array([b.h for b in bars])
    lows = np.array([b.l for b in bars])
    volumes = np.array([getattr(b, "v", 0.0) for b in bars])

    return scan_patterns(closes, highs, lows, volumes)
