import pytest
from app.services.screener import _adaptive_pre_screen

def test_adaptive_gate_monotonic():
    # Linear drop, no major gaps. Should fallback to statistical mean.
    # Scores: 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2
    # Mean = 0.55. Should keep >= 0.55 -> [0.9, 0.8, 0.7, 0.6] (4 candidates)
    # But wait, min_candidates is 5. So it should keep 5 candidates -> down to 0.5.
    scores = [(i, round(0.9 - (0.1 * i), 2)) for i in range(8)]
    passed = _adaptive_pre_screen(scores, min_keep=5, max_keep=20, gap_threshold=0.15)
    assert len(passed) == 5
    assert passed[-1][1] == 0.5

def test_adaptive_gate_bimodal_gap():
    # Top 3 are great (~0.9), rest are terrible (~0.4)
    scores = [(0, 0.95), (1, 0.92), (2, 0.90), (3, 0.40), (4, 0.38), (5, 0.35), (6, 0.30)]
    passed = _adaptive_pre_screen(scores, min_keep=2, max_keep=10, gap_threshold=0.1)
    # Gap is 0.5 between 0.90 and 0.40. Should cutoff at 0.90.
    assert len(passed) == 3
    assert passed[-1][1] == 0.90

def test_adaptive_gate_clustered_high():
    # All are very good and tightly clustered.
    # Mean is ~0.92. Should fallback to mean or max_keep.
    scores = [(i, 0.95 - (i * 0.01)) for i in range(15)]
    # Min keep = 5.
    passed = _adaptive_pre_screen(scores, min_keep=5, max_keep=10, gap_threshold=0.1)
    # Since gap max is 0.01, it uses mean cutoff. Mean = 0.89.
    # Scores above mean: 0.95, 0.94, ..., 0.89 (7 candidates).
    assert len(passed) == 7

def test_adaptive_gate_small_set():
    # Fewer than min_keep candidates. All should pass.
    scores = [(0, 0.8), (1, 0.7), (2, 0.6)]
    passed = _adaptive_pre_screen(scores, min_keep=5, max_keep=20, gap_threshold=0.05)
    assert len(passed) == 3

def test_adaptive_gate_ceiling():
    # Huge number of great candidates. Should cap at max_keep.
    scores = [(i, 0.90 - (i * 0.001)) for i in range(50)]
    passed = _adaptive_pre_screen(scores, min_keep=5, max_keep=10, gap_threshold=0.1)
    assert len(passed) == 10
