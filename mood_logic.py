from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd


ENTRY_COLUMNS = [
    "id",
    "created_at",
    "user_name",
    "mood_score",
    "mood_label",
    "note",
]
MOOD_LABELS = ["开心", "平静", "焦虑", "疲惫", "低落", "兴奋"]
APP_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class MoodSummary:
    record_count: int
    average_score: float | None
    latest_score: int | None
    latest_label: str | None
    common_label: str | None
    current_streak: int
    seven_day_change: float | None


def normalize_entries(entries: pd.DataFrame) -> pd.DataFrame:
    """Return a predictable, timezone-aware mood-entry dataframe."""

    if entries.empty:
        return pd.DataFrame(columns=ENTRY_COLUMNS + ["entry_date"])

    normalized = entries.copy()
    for column in ENTRY_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = None

    normalized["created_at"] = pd.to_datetime(
        normalized["created_at"], errors="coerce", utc=True
    )
    normalized = normalized.dropna(subset=["created_at"])
    normalized["mood_score"] = pd.to_numeric(
        normalized["mood_score"], errors="coerce"
    ).astype("Int64")
    normalized["user_name"] = normalized["user_name"].fillna("").astype(str)
    normalized["mood_label"] = normalized["mood_label"].fillna("").astype(str)
    normalized["note"] = normalized["note"].fillna("").astype(str)
    normalized["entry_date"] = (
        normalized["created_at"].dt.tz_convert(APP_TIMEZONE).dt.date
    )
    return normalized[ENTRY_COLUMNS + ["entry_date"]].sort_values(
        "created_at", ascending=False
    )


def build_demo_dataframe(today: date | None = None) -> pd.DataFrame:
    """Create stable example data for the default demo profile."""

    current_day = today or date.today()
    labels = [
        "平静",
        "开心",
        "疲惫",
        "焦虑",
        "平静",
        "兴奋",
        "低落",
        "平静",
        "开心",
        "疲惫",
    ]
    scores = [6, 8, 5, 4, 7, 9, 4, 6, 8, 5]
    notes = [
        "把今天最重要的事情推进了一步。",
        "和朋友聊了很久，感觉被理解。",
        "睡眠不足，下午有些疲惫。",
        "事情有点多，需要重新排优先级。",
        "散步以后，心情慢慢平稳下来。",
    ]
    rows: list[dict[str, Any]] = []

    for index in range(30):
        day = current_day - timedelta(days=29 - index)
        rows.append(
            {
                "id": index + 1,
                "created_at": datetime.combine(
                    day, datetime.min.time().replace(hour=12), tzinfo=timezone.utc
                ),
                "user_name": "demo_user",
                "mood_score": scores[index % len(scores)],
                "mood_label": labels[index % len(labels)],
                "note": notes[index % len(notes)],
            }
        )

    return normalize_entries(pd.DataFrame(rows))


def filter_entries(entries: pd.DataFrame, user_name: str) -> pd.DataFrame:
    """Filter records to one profile using a case-insensitive exact match."""

    normalized_name = user_name.strip().casefold()
    if not normalized_name or entries.empty:
        return pd.DataFrame(columns=ENTRY_COLUMNS + ["entry_date"])

    names = entries["user_name"].astype(str).str.strip().str.casefold()
    return entries[names == normalized_name].copy()


def entries_for_period(
    entries: pd.DataFrame, days: int, today: date | None = None
) -> pd.DataFrame:
    """Return records within an inclusive rolling date window."""

    if entries.empty:
        return entries.copy()

    current_day = today or date.today()
    start_date = current_day - timedelta(days=days - 1)
    return entries[entries["entry_date"] >= start_date].copy()


def daily_average(
    entries: pd.DataFrame, days: int, today: date | None = None
) -> pd.DataFrame:
    """Return one average score per day for the requested period."""

    recent = entries_for_period(entries, days, today)
    if recent.empty:
        return pd.DataFrame(columns=["entry_date", "average_mood_score"])

    valid = recent.dropna(subset=["mood_score"])
    grouped = (
        valid.groupby("entry_date", as_index=False)["mood_score"]
        .mean()
        .rename(columns={"mood_score": "average_mood_score"})
        .sort_values("entry_date")
    )
    grouped["entry_date"] = pd.to_datetime(grouped["entry_date"])
    return grouped


def calculate_current_streak(
    entries: pd.DataFrame, today: date | None = None
) -> int:
    """Count consecutive recording days ending today or yesterday."""

    if entries.empty:
        return 0

    current_day = today or date.today()
    recorded_days = sorted(set(entries["entry_date"].dropna()), reverse=True)
    if not recorded_days or recorded_days[0] < current_day - timedelta(days=1):
        return 0

    streak = 1
    expected_day = recorded_days[0] - timedelta(days=1)
    for recorded_day in recorded_days[1:]:
        if recorded_day == expected_day:
            streak += 1
            expected_day -= timedelta(days=1)
        elif recorded_day < expected_day:
            break
    return streak


def calculate_summary(
    entries: pd.DataFrame, today: date | None = None
) -> MoodSummary:
    """Calculate descriptive statistics without making clinical claims."""

    if entries.empty:
        return MoodSummary(0, None, None, None, None, 0, None)

    valid = entries.dropna(subset=["mood_score"]).sort_values(
        "created_at", ascending=False
    )
    if valid.empty:
        return MoodSummary(len(entries), None, None, None, None, 0, None)

    current_day = today or date.today()
    recent_week = entries_for_period(valid, 7, current_day)
    previous_start = current_day - timedelta(days=13)
    previous_end = current_day - timedelta(days=7)
    previous_week = valid[
        (valid["entry_date"] >= previous_start)
        & (valid["entry_date"] <= previous_end)
    ]
    change = None
    if not recent_week.empty and not previous_week.empty:
        change = float(
            recent_week["mood_score"].mean() - previous_week["mood_score"].mean()
        )

    common_label = valid["mood_label"].replace("", pd.NA).mode()
    latest = valid.iloc[0]
    return MoodSummary(
        record_count=len(valid),
        average_score=float(valid["mood_score"].mean()),
        latest_score=int(latest["mood_score"]),
        latest_label=str(latest["mood_label"]) or None,
        common_label=(
            str(common_label.iloc[0]) if not common_label.empty else None
        ),
        current_streak=calculate_current_streak(valid, current_day),
        seven_day_change=change,
    )


def score_description(score: int) -> tuple[str, str]:
    """Map a score to an emoji and plain-language state."""

    if score <= 2:
        return "🌧️", "今天似乎很不容易"
    if score <= 4:
        return "🌥️", "状态偏低，先照顾好自己"
    if score <= 6:
        return "⛅", "状态一般，可以慢一点"
    if score <= 8:
        return "🌤️", "整体不错，留意是什么带来了帮助"
    return "☀️", "今天能量很好，值得记住"


def reflection_text(summary: MoodSummary) -> str:
    """Generate a restrained, non-diagnostic reflection prompt."""

    if summary.record_count == 0:
        return "从今天开始记录。几天后再回来，你会更容易看见变化。"
    if summary.record_count < 4:
        return "已经有了一个开始。连续记录几天，比急着解释一次波动更有价值。"
    if summary.seven_day_change is None:
        return "继续记录一周，届时可以把本周与上一周放在一起观察。"
    if summary.seven_day_change >= 0.8:
        return "最近 7 天的平均分有所上升。回看备注，找找哪些人或事情可能带来了帮助。"
    if summary.seven_day_change <= -0.8:
        return "最近 7 天的平均分有所下降。先关注睡眠、压力和支持系统，不必急着给自己下结论。"
    return "最近两周整体较平稳。可以继续留意高分日与低分日分别发生了什么。"
