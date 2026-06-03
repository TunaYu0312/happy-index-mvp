from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st


MOOD_LABELS = ["开心", "平静", "焦虑", "疲惫", "低落", "兴奋"]
TABLE_NAME = "happy_index_entries"


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings loaded from Streamlit secrets."""

    url: str | None = None
    host: str | None = None
    port: int = 5432
    database: str | None = None
    user: str | None = None
    password: str | None = None
    sslmode: str = "require"

    @property
    def is_complete(self) -> bool:
        if self.url:
            return True
        return all([self.host, self.database, self.user, self.password])


def get_database_config() -> DatabaseConfig | None:
    """Read database config from st.secrets without requiring local secrets."""

    try:
        database_secrets = st.secrets.get("database", {})
    except Exception:
        return None

    if not database_secrets:
        return None

    config = DatabaseConfig(
        url=database_secrets.get("url"),
        host=database_secrets.get("host"),
        port=int(database_secrets.get("port", 5432)),
        database=database_secrets.get("dbname")
        or database_secrets.get("database"),
        user=database_secrets.get("user"),
        password=database_secrets.get("password"),
        sslmode=database_secrets.get("sslmode", "require"),
    )
    return config if config.is_complete else None


def connect_to_database(config: DatabaseConfig):
    """Open a PostgreSQL connection using a URL or individual fields."""

    if config.url:
        return psycopg2.connect(config.url, sslmode=config.sslmode)

    return psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.database,
        user=config.user,
        password=config.password,
        sslmode=config.sslmode,
    )


def insert_mood_entry(
    config: DatabaseConfig,
    user_name: str,
    mood_score: int,
    mood_label: str,
    note: str,
) -> None:
    """Persist one mood entry into PostgreSQL."""

    query = f"""
        INSERT INTO {TABLE_NAME} (user_name, mood_score, mood_label, note)
        VALUES (%s, %s, %s, %s)
    """
    with connect_to_database(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (user_name, mood_score, mood_label, note))


def load_mood_entries(config: DatabaseConfig) -> pd.DataFrame:
    """Load mood entries for charts and recent-record display."""

    query = f"""
        SELECT id, created_at, user_name, mood_score, mood_label, note
        FROM {TABLE_NAME}
        ORDER BY created_at DESC
        LIMIT 300
    """
    with connect_to_database(config) as connection:
        with connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(query)
            rows: list[dict[str, Any]] = cursor.fetchall()

    return normalize_entries(pd.DataFrame(rows))


def build_demo_dataframe() -> pd.DataFrame:
    """Create deterministic demo data for Streamlit Cloud without secrets."""

    today = date.today()
    labels = ["平静", "开心", "疲惫", "焦虑", "兴奋", "低落", "平静"]
    scores = [7, 8, 5, 4, 9, 3, 7]
    rows: list[dict[str, Any]] = []

    for index in range(30):
        day = today - timedelta(days=29 - index)
        label = labels[index % len(labels)]
        score = max(1, min(10, scores[index % len(scores)] + ((index % 3) - 1)))
        rows.append(
            {
                "id": index + 1,
                "created_at": datetime.combine(
                    day, datetime.min.time(), tzinfo=timezone.utc
                ),
                "user_name": "demo_user",
                "mood_score": score,
                "mood_label": label,
                "note": "Demo 模式示例记录",
            }
        )

    return normalize_entries(pd.DataFrame(rows).sort_values("created_at", ascending=False))


def normalize_entries(entries: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected columns and datetime fields exist."""

    columns = ["id", "created_at", "user_name", "mood_score", "mood_label", "note"]
    if entries.empty:
        return pd.DataFrame(columns=columns + ["entry_date"])

    normalized = entries.copy()
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = None

    normalized["created_at"] = pd.to_datetime(normalized["created_at"], errors="coerce")
    normalized = normalized.dropna(subset=["created_at"])
    normalized["mood_score"] = pd.to_numeric(
        normalized["mood_score"], errors="coerce"
    ).astype("Int64")
    normalized["entry_date"] = normalized["created_at"].dt.date
    return normalized[columns + ["entry_date"]]


def daily_average(entries: pd.DataFrame, days: int) -> pd.DataFrame:
    """Return average mood by day for the requested period."""

    if entries.empty:
        return pd.DataFrame(columns=["entry_date", "average_mood_score"])

    start_date = date.today() - timedelta(days=days - 1)
    recent = entries[entries["entry_date"] >= start_date]
    grouped = (
        recent.groupby("entry_date", as_index=False)["mood_score"]
        .mean()
        .rename(columns={"mood_score": "average_mood_score"})
        .sort_values("entry_date")
    )
    grouped["entry_date"] = pd.to_datetime(grouped["entry_date"])
    return grouped


def render_trend_chart(entries: pd.DataFrame, days: int) -> None:
    """Render a daily average mood trend chart."""

    trend = daily_average(entries, days)
    if trend.empty:
        st.info(f"最近 {days} 天暂无心情记录。")
        return

    chart_data = trend.set_index("entry_date")["average_mood_score"]
    st.line_chart(chart_data, height=280, y_label="平均心情分")


def render_label_distribution(entries: pd.DataFrame) -> None:
    """Render mood label distribution."""

    if entries.empty:
        st.info("暂无心情标签记录。")
        return

    distribution = (
        entries.groupby("mood_label", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )
    chart_data = distribution.set_index("mood_label")["count"]
    st.bar_chart(chart_data, height=280, y_label="记录数")


def render_insights(entries: pd.DataFrame) -> None:
    """Render simple insight cards."""

    if entries.empty:
        st.info("提交第一条记录后，这里会生成心情洞察。")
        return

    valid_scores = entries.dropna(subset=["mood_score"])
    current_average = valid_scores["mood_score"].mean()
    latest = entries.sort_values("created_at", ascending=False).iloc[0]
    most_common_label = entries["mood_label"].mode()

    week_start = date.today() - timedelta(days=6)
    this_week = valid_scores[valid_scores["entry_date"] >= week_start]
    if this_week.empty:
        lowest_day_text = "最近 7 天暂无记录"
    else:
        lowest_record = this_week.sort_values(["mood_score", "created_at"]).iloc[0]
        lowest_day_text = (
            f"{lowest_record['entry_date']}（{int(lowest_record['mood_score'])} 分）"
        )

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("当前平均心情分", f"{current_average:.2f}")
    col_b.metric("最近一次记录", f"{int(latest['mood_score'])} 分")
    col_c.metric(
        "最常见心情标签",
        most_common_label.iloc[0] if not most_common_label.empty else "暂无",
    )
    col_d.metric("本周最低心情日期", lowest_day_text)

    with st.expander("最近一次记录详情", expanded=False):
        st.write(
            {
                "昵称": latest["user_name"],
                "心情标签": latest["mood_label"],
                "备注": latest["note"] or "无",
                "记录时间": latest["created_at"],
            }
        )


def render_entry_form(config: DatabaseConfig | None, demo_mode: bool) -> None:
    """Render the mood-entry form and handle submit."""

    with st.form("mood_entry_form", clear_on_submit=True):
        user_name = st.text_input("昵称 user_name", max_chars=40)
        mood_score = st.slider("心情分数 mood_score", min_value=1, max_value=10, value=7)
        mood_label = st.selectbox("心情标签 mood_label", MOOD_LABELS)
        note = st.text_area("一句话备注 note", max_chars=200)
        submitted = st.form_submit_button("提交记录")

    if not submitted:
        return

    if not user_name.strip():
        st.warning("请先填写昵称。")
        return

    if demo_mode or config is None:
        st.info("当前为 demo 模式：未配置数据库，提交不会写入持久化数据库。")
        return

    try:
        insert_mood_entry(
            config=config,
            user_name=user_name.strip(),
            mood_score=mood_score,
            mood_label=mood_label,
            note=note.strip(),
        )
    except Exception as error:
        st.error(f"写入数据库失败：{error}")
    else:
        st.success("记录已提交。")
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=60)
def load_entries_cached(database_available: bool) -> pd.DataFrame:
    """Load entries with a short cache to keep the app responsive."""

    config = get_database_config()
    if not database_available or config is None:
        return build_demo_dataframe()
    return load_mood_entries(config)


def main() -> None:
    st.set_page_config(
        page_title="Happy Index 心情指数",
        page_icon="💛",
        layout="wide",
    )

    st.title("Happy Index 心情指数")
    st.caption("每天记录一个 1-10 分的心情指数，观察自己的情绪趋势。")

    config = get_database_config()
    demo_mode = config is None

    if demo_mode:
        st.warning(
            "Demo 模式：当前未检测到 Streamlit secrets 中的数据库配置，"
            "页面使用本地示例数据展示，提交不会写入数据库。"
        )
    else:
        st.success("数据库模式：已检测到数据库配置，提交记录会写入 PostgreSQL/Supabase。")

    try:
        entries = load_entries_cached(database_available=not demo_mode)
    except Exception as error:
        st.error(f"读取数据库失败，已切换为 demo 数据展示：{error}")
        demo_mode = True
        entries = build_demo_dataframe()

    st.subheader("记录今天的心情")
    render_entry_form(config=config, demo_mode=demo_mode)

    st.divider()
    st.subheader("简单洞察")
    render_insights(entries)

    st.divider()
    trend_tab_7, trend_tab_30, label_tab, recent_tab = st.tabs(
        ["最近 7 天趋势", "最近 30 天趋势", "心情标签分布", "最近 30 条记录"]
    )

    with trend_tab_7:
        render_trend_chart(entries, days=7)

    with trend_tab_30:
        render_trend_chart(entries, days=30)

    with label_tab:
        render_label_distribution(entries)

    with recent_tab:
        recent_columns = [
            "created_at",
            "user_name",
            "mood_score",
            "mood_label",
            "note",
        ]
        recent_entries = (
            entries.sort_values("created_at", ascending=False)
            .head(30)
            .loc[:, recent_columns]
        )
        st.dataframe(recent_entries, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
