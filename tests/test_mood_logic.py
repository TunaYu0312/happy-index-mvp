from datetime import date, datetime, timedelta, timezone
import unittest

import pandas as pd

from mood_logic import (
    build_demo_dataframe,
    calculate_current_streak,
    calculate_summary,
    daily_average,
    filter_entries,
    normalize_entries,
    score_description,
)


class MoodLogicTests(unittest.TestCase):
    def test_demo_data_has_thirty_normalized_rows(self):
        entries = build_demo_dataframe(date(2026, 7, 28))

        self.assertEqual(len(entries), 30)
        self.assertIn("entry_date", entries.columns)
        self.assertEqual(entries["mood_score"].min(), 4)
        self.assertEqual(entries["mood_score"].max(), 9)

    def test_filter_entries_is_case_insensitive_and_exact(self):
        entries = normalize_entries(
            pd.DataFrame(
                [
                    {
                        "created_at": datetime.now(timezone.utc),
                        "user_name": "Tuna",
                        "mood_score": 8,
                        "mood_label": "开心",
                        "note": "",
                    },
                    {
                        "created_at": datetime.now(timezone.utc),
                        "user_name": "Tuna-2",
                        "mood_score": 5,
                        "mood_label": "平静",
                        "note": "",
                    },
                ]
            )
        )

        filtered = filter_entries(entries, " tuna ")

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["user_name"], "Tuna")

    def test_streak_counts_consecutive_days(self):
        today = date(2026, 7, 28)
        rows = []
        for offset in [0, 1, 2, 4]:
            rows.append(
                {
                    "created_at": datetime.combine(
                        today - timedelta(days=offset),
                        datetime.min.time().replace(hour=12),
                        tzinfo=timezone.utc,
                    ),
                    "user_name": "Tuna",
                    "mood_score": 7,
                    "mood_label": "平静",
                    "note": "",
                }
            )
        entries = normalize_entries(pd.DataFrame(rows))

        self.assertEqual(calculate_current_streak(entries, today), 3)

    def test_summary_compares_two_seven_day_windows(self):
        today = date(2026, 7, 28)
        rows = []
        for offset in range(14):
            score = 8 if offset < 7 else 5
            rows.append(
                {
                    "created_at": datetime.combine(
                        today - timedelta(days=offset),
                        datetime.min.time().replace(hour=12),
                        tzinfo=timezone.utc,
                    ),
                    "user_name": "Tuna",
                    "mood_score": score,
                    "mood_label": "平静",
                    "note": "",
                }
            )
        entries = normalize_entries(pd.DataFrame(rows))

        summary = calculate_summary(entries, today)

        self.assertEqual(summary.record_count, 14)
        self.assertAlmostEqual(summary.seven_day_change, 3.0)

    def test_daily_average_collapses_multiple_entries_per_day(self):
        today = date(2026, 7, 28)
        entries = normalize_entries(
            pd.DataFrame(
                [
                    {
                        "created_at": datetime.combine(
                            today,
                            datetime.min.time().replace(hour=2),
                            tzinfo=timezone.utc,
                        ),
                        "user_name": "Tuna",
                        "mood_score": 4,
                        "mood_label": "疲惫",
                        "note": "",
                    },
                    {
                        "created_at": datetime.combine(
                            today,
                            datetime.min.time().replace(hour=8),
                            tzinfo=timezone.utc,
                        ),
                        "user_name": "Tuna",
                        "mood_score": 8,
                        "mood_label": "开心",
                        "note": "",
                    },
                ]
            )
        )

        trend = daily_average(entries, 7, today)

        self.assertEqual(len(trend), 1)
        self.assertEqual(trend.iloc[0]["average_mood_score"], 6)

    def test_score_description_covers_scale_boundaries(self):
        self.assertEqual(score_description(1)[0], "🌧️")
        self.assertEqual(score_description(10)[0], "☀️")


if __name__ == "__main__":
    unittest.main()
