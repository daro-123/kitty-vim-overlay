import statistics
import timeit
import unittest

from kitty_scrollback_navigator.model import ScrollbackModel
from kitty_scrollback_navigator.search import SearchState
from kitty_scrollback_navigator.snapshot import viewport_start


def _median_seconds(function, *, number=3, repeat=5):
    return statistics.median(timeit.repeat(function, number=number, repeat=repeat)) / number


def _reference_viewport_start(history, screen):
    if len(screen) > len(history):
        raise ValueError("Kitty screen text is longer than its retained history")
    for start in range(len(history) - len(screen), -1, -1):
        if history[start : start + len(screen)] == screen:
            return start
    raise ValueError("Could not align Kitty's visible screen with its retained history")


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_visible_search_matching_is_faster_than_scanning_full_history(self):
        model = ScrollbackModel(
            tuple(f"row {index:06d} INFO payload" for index in range(100_000)),
            viewport_height=40,
        )
        search = SearchState(model)
        visible_rows = range(50_000, 50_040)

        full_scan_seconds = _median_seconds(
            lambda: search.match_positions("INFO")
        )
        visible_scan_seconds = _median_seconds(
            lambda: search.match_positions("INFO", rows=visible_rows)
        )
        print(
            "search benchmark (100,000 rows): "
            f"full={full_scan_seconds * 1_000:.3f} ms, "
            f"visible-40={visible_scan_seconds * 1_000:.3f} ms, "
            f"speedup={full_scan_seconds / visible_scan_seconds:.1f}x"
        )

        self.assertLess(
            visible_scan_seconds,
            full_scan_seconds / 4,
            f"visible={visible_scan_seconds:.6f}s full={full_scan_seconds:.6f}s",
        )

    def test_viewport_alignment_is_faster_than_slice_comparison_baseline(self):
        history = tuple(f"row-{index:06d}" for index in range(100_000))
        screen = history[:40]

        baseline_seconds = _median_seconds(
            lambda: _reference_viewport_start(history, screen)
        )
        optimized_seconds = _median_seconds(
            lambda: viewport_start(history, screen)
        )
        print(
            "viewport alignment benchmark (100,000 history / 40 screen rows): "
            f"slice baseline={baseline_seconds * 1_000:.3f} ms, "
            f"KMP={optimized_seconds * 1_000:.3f} ms, "
            f"speedup={baseline_seconds / optimized_seconds:.1f}x"
        )

        self.assertLess(
            optimized_seconds,
            baseline_seconds / 2,
            f"optimized={optimized_seconds:.6f}s baseline={baseline_seconds:.6f}s",
        )


if __name__ == "__main__":
    unittest.main()
