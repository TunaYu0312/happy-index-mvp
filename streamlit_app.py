from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

from mood_logic import (
    APP_TIMEZONE,
    ENTRY_COLUMNS,
    MOOD_LABELS,
    build_demo_dataframe,
    calculate_summary,
    daily_average,
    entries_for_period,
    filter_entries,
    normalize_entries,
    reflection_text,
    score_description,
)


TABLE_NAME = "happy_index_entries"
MOOD_EMOJI = {
    "开心": "😊",
    "平静": "😌",
    "焦虑": "😟",
    "疲惫": "😮‍💨",
    "低落": "😔",
    "兴奋": "🤩",
}


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
    """Read database settings without requiring local secrets."""

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
            cursor.execute(
                query,
                (user_name, mood_score, mood_label, note),
            )


def load_mood_entries(
    config: DatabaseConfig, user_name: str
) -> pd.DataFrame:
    """Load one profile's entries instead of exposing every user's records."""

    query = f"""
        SELECT id, created_at, user_name, mood_score, mood_label, note
        FROM {TABLE_NAME}
        WHERE lower(trim(user_name)) = lower(trim(%s))
        ORDER BY created_at DESC
        LIMIT 500
    """
    with connect_to_database(config) as connection:
        with connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(query, (user_name,))
            rows: list[dict[str, Any]] = cursor.fetchall()
    return normalize_entries(pd.DataFrame(rows))


@st.cache_data(ttl=60, show_spinner=False)
def load_entries_cached(
    database_available: bool, user_name: str
) -> pd.DataFrame:
    """Load one profile with a short cache for responsive reruns."""

    if not user_name.strip():
        return pd.DataFrame(columns=ENTRY_COLUMNS + ["entry_date"])

    config = get_database_config()
    if not database_available or config is None:
        return filter_entries(build_demo_dataframe(), user_name)
    return load_mood_entries(config, user_name)


def inject_styles() -> None:
    """Apply a restrained visual system while keeping native controls."""

    st.markdown(
        """
        <style>
        :root {
            --ink: #24332D;
            --muted: #64736D;
            --line: #DFE7E2;
            --paper: #FFFFFF;
            --wash: #F4F8F5;
            --brand: #2E6B52;
            --accent: #F0B75B;
        }
        .stApp {
            background:
                radial-gradient(circle at 85% 4%, rgba(240,183,91,.14), transparent 25rem),
                linear-gradient(180deg, #F8FBF9 0%, #F4F8F5 100%);
            color: var(--ink);
        }
        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3 { color: var(--ink); letter-spacing: -0.02em; }
        .app-kicker {
            color: var(--brand);
            font-size: .82rem;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: .45rem;
        }
        .app-title {
            color: var(--ink);
            font-size: clamp(2rem, 5vw, 3.25rem);
            font-weight: 760;
            line-height: 1.08;
            letter-spacing: -.045em;
            margin: 0;
        }
        .app-subtitle {
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.7;
            max-width: 42rem;
            margin-top: .8rem;
        }
        .soft-card {
            background: rgba(255,255,255,.88);
            border: 1px solid var(--line);
            border-radius: 20px;
            box-shadow: 0 14px 34px rgba(40,72,58,.06);
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
        }
        .soft-card-label {
            color: var(--muted);
            font-size: .82rem;
            font-weight: 650;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .soft-card-value {
            color: var(--ink);
            font-size: 1.45rem;
            font-weight: 720;
            margin: .35rem 0;
        }
        .soft-card-copy { color: var(--muted); line-height: 1.55; }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,.86);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 1rem 1.05rem;
            box-shadow: 0 8px 20px rgba(40,72,58,.04);
        }
        div[data-testid="stMetricLabel"] { color: var(--muted); }
        div[data-testid="stForm"] {
            background: rgba(255,255,255,.9);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 1.25rem;
            box-shadow: 0 14px 34px rgba(40,72,58,.05);
        }
        .stButton > button, .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 44px;
            border-radius: 12px;
            font-weight: 650;
        }
        div[data-testid="stFormSubmitButton"] > button {
            background: var(--brand);
            border-color: var(--brand);
            color: white;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: #245841;
            border-color: #245841;
            color: white;
        }
        div[data-testid="stAlert"] { border-radius: 14px; }
        div[data-testid="stTabs"] button { min-height: 44px; }
        [data-testid="stSidebar"] {
            background: rgba(250,252,250,.96);
            border-right: 1px solid var(--line);
        }
        @media (max-width: 700px) {
            .block-container { padding: 1.2rem 1rem 3rem; }
            .app-title { font-size: 2.25rem; }
            .soft-card { border-radius: 16px; padding: 1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session() -> None:
    """Initialize lightweight demo persistence and profile state."""

    if "demo_entries" not in st.session_state:
        st.session_state.demo_entries = []
    if "active_user" not in st.session_state:
        st.session_state.active_user = "demo_user"
    if "entry_saved" not in st.session_state:
        st.session_state.entry_saved = False


def combine_demo_entries(entries: pd.DataFrame) -> pd.DataFrame:
    """Merge this browser session's demo submissions into example data."""

    if not st.session_state.demo_entries:
        return entries
    session_entries = normalize_entries(
        pd.DataFrame(st.session_state.demo_entries)
    )
    return normalize_entries(pd.concat([entries, session_entries]))


def render_header(demo_mode: bool) -> None:
    mode_text = "可交互演示" if demo_mode else "数据库已连接"
    st.markdown(
        f"""
        <div class="app-kicker">Daily emotional check-in · {mode_text}</div>
        <h1 class="app-title">Happy Index<br>心情指数</h1>
        <p class="app-subtitle">
            用一分钟记录今天的感受。这里帮助你看见变化、回顾原因，
            不评判情绪，也不替代专业心理支持。
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(demo_mode: bool) -> str:
    """Render identity, mode information, and data boundaries."""

    with st.sidebar:
        st.markdown("### 个人空间")
        user_name = st.text_input(
            "你的昵称",
            key="active_user",
            max_chars=40,
            help="昵称用于查找你的记录。当前 MVP 尚未提供账号登录。",
        )
        if demo_mode:
            st.info(
                "当前是演示模式。你提交的记录只保存在本次浏览会话中，刷新服务后可能消失。"
            )
        else:
            st.success("数据库已连接，提交后会保存。")

        st.markdown("---")
        st.caption(
            "隐私提醒：昵称不是身份验证。正式公开使用前，应增加账号登录和数据访问控制。"
        )
    return user_name.strip()


def render_today_status(entries: pd.DataFrame) -> None:
    """Show whether the active profile has checked in today."""

    today_entries = entries[entries["entry_date"] == date.today()]
    if today_entries.empty:
        st.markdown(
            """
            <div class="soft-card">
                <div class="soft-card-label">Today · 今天</div>
                <div class="soft-card-value">还没有记录</div>
                <div class="soft-card-copy">停一会儿，按真实感受选择，不必选“应该有的心情”。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    latest = today_entries.sort_values("created_at", ascending=False).iloc[0]
    emoji, description = score_description(int(latest["mood_score"]))
    label_emoji = MOOD_EMOJI.get(str(latest["mood_label"]), "•")
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="soft-card-label">Today · 已记录</div>
            <div class="soft-card-value">
                {emoji} {int(latest["mood_score"])} / 10
                · {label_emoji} {latest["mood_label"]}
            </div>
            <div class="soft-card-copy">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_entry_form(
    config: DatabaseConfig | None, demo_mode: bool, user_name: str
) -> None:
    """Render a short daily check-in and persist one submission."""

    st.markdown("### 记录此刻")
    st.caption("约 1 分钟完成。心情没有正确答案，分数只代表你此刻的主观感受。")

    with st.form("mood_entry_form", clear_on_submit=True):
        mood_score = st.slider(
            "此刻的心情分数",
            min_value=1,
            max_value=10,
            value=6,
            help="1 代表非常低落，10 代表状态很好。",
        )
        mood_label = st.radio(
            "最接近哪种感受？",
            MOOD_LABELS,
            horizontal=True,
            format_func=lambda label: f"{MOOD_EMOJI[label]} {label}",
        )
        note = st.text_area(
            "发生了什么？（可选）",
            placeholder="一句话就好，例如：完成了拖延很久的事，感觉轻松了一些。",
            max_chars=200,
        )
        submitted = st.form_submit_button(
            "保存今天的心情",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return
    if not user_name:
        st.warning("请先在左侧填写昵称，再保存记录。")
        return

    if demo_mode or config is None:
        st.session_state.demo_entries.append(
            {
                "id": f"session-{len(st.session_state.demo_entries) + 1}",
                "created_at": datetime.now(timezone.utc),
                "user_name": user_name,
                "mood_score": mood_score,
                "mood_label": mood_label,
                "note": note.strip(),
            }
        )
        st.session_state.entry_saved = True
        st.rerun()

    try:
        insert_mood_entry(
            config=config,
            user_name=user_name,
            mood_score=mood_score,
            mood_label=mood_label,
            note=note.strip(),
        )
    except Exception:
        st.error("保存失败，请稍后重试。数据库详细错误未显示，以避免泄露连接信息。")
    else:
        st.session_state.entry_saved = True
        st.cache_data.clear()
        st.rerun()


def render_summary(entries: pd.DataFrame) -> None:
    """Render compact, descriptive insights."""

    summary = calculate_summary(entries)
    st.markdown("### 你的近况")
    if summary.record_count == 0:
        st.info("保存第一条记录后，这里会逐步形成只属于你的趋势。")
        return

    average = (
        f"{summary.average_score:.1f} / 10"
        if summary.average_score is not None
        else "—"
    )
    change = (
        f"{summary.seven_day_change:+.1f}"
        if summary.seven_day_change is not None
        else "数据不足"
    )
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("全部记录", f"{summary.record_count} 次")
    col_b.metric("平均心情", average)
    col_c.metric("连续记录", f"{summary.current_streak} 天")
    col_d.metric("近 7 天变化", change, help="最近 7 天均值减去此前 7 天均值")

    st.markdown(
        f"""
        <div class="soft-card">
            <div class="soft-card-label">Reflection · 温和回看</div>
            <div class="soft-card-copy">{reflection_text(summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trend_chart(entries: pd.DataFrame, days: int) -> None:
    trend = daily_average(entries, days)
    if trend.empty:
        st.info(f"最近 {days} 天暂无记录。")
        return

    chart_data = trend.set_index("entry_date")[["average_mood_score"]]
    st.line_chart(
        chart_data,
        height=320,
        color=["#2E6B52"],
        y_label="平均心情分",
    )
    st.caption("每日多次记录会先计算当天平均值；分数仅反映主观感受。")


def render_distribution(entries: pd.DataFrame, days: int) -> None:
    recent = entries_for_period(entries, days)
    if recent.empty:
        st.info(f"最近 {days} 天暂无标签记录。")
        return

    distribution = (
        recent.groupby("mood_label", as_index=False)
        .size()
        .rename(columns={"size": "记录次数"})
        .sort_values("记录次数", ascending=False)
    )
    distribution["感受"] = distribution["mood_label"].map(
        lambda label: f"{MOOD_EMOJI.get(label, '•')} {label}"
    )
    st.bar_chart(
        distribution.set_index("感受")[["记录次数"]],
        height=320,
        color=["#F0B75B"],
        y_label="记录次数",
    )


def render_history(entries: pd.DataFrame) -> None:
    if entries.empty:
        st.info("暂无记录。")
        return

    display = entries.sort_values("created_at", ascending=False).head(100).copy()
    display["日期"] = (
        display["created_at"]
        .dt.tz_convert(APP_TIMEZONE)
        .dt.strftime("%Y-%m-%d %H:%M")
    )
    display["分数"] = display["mood_score"]
    display["感受"] = display["mood_label"].map(
        lambda label: f"{MOOD_EMOJI.get(label, '•')} {label}"
    )
    display["备注"] = display["note"].replace("", "—")
    st.dataframe(
        display[["日期", "分数", "感受", "备注"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "分数": st.column_config.ProgressColumn(
                "分数", min_value=1, max_value=10, format="%d"
            )
        },
    )

    export = display[["日期", "分数", "mood_label", "备注"]].rename(
        columns={"mood_label": "心情标签"}
    )
    st.download_button(
        "导出 CSV",
        data=export.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"happy-index-{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=False,
    )


def render_explore(entries: pd.DataFrame) -> None:
    """Render one compact exploration area instead of four competing tabs."""

    st.markdown("### 看见变化")
    period = st.segmented_control(
        "时间范围",
        options=[7, 30, 90],
        default=30,
        format_func=lambda value: f"{value} 天",
        label_visibility="collapsed",
    )
    selected_days = int(period or 30)

    trend_tab, label_tab, history_tab = st.tabs(
        ["趋势", "感受分布", "记录"]
    )
    with trend_tab:
        render_trend_chart(entries, selected_days)
    with label_tab:
        render_distribution(entries, selected_days)
    with history_tab:
        render_history(entries)


def main() -> None:
    st.set_page_config(
        page_title="Happy Index · 心情指数",
        page_icon="🌤️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    initialize_session()

    config = get_database_config()
    demo_mode = config is None
    user_name = render_sidebar(demo_mode)
    render_header(demo_mode)

    if st.session_state.entry_saved:
        st.success("已保存。谢谢你认真看见了此刻的自己。")
        st.session_state.entry_saved = False

    try:
        entries = load_entries_cached(
            database_available=not demo_mode,
            user_name=user_name,
        )
    except Exception:
        st.error("暂时无法读取数据库，已切换到演示数据。")
        demo_mode = True
        entries = filter_entries(build_demo_dataframe(), user_name)

    if demo_mode:
        entries = combine_demo_entries(entries)
        entries = filter_entries(entries, user_name)

    st.write("")
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        render_entry_form(config, demo_mode, user_name)
    with right:
        render_today_status(entries)
        st.markdown(
            """
            <div class="soft-card">
                <div class="soft-card-label">A small reminder</div>
                <div class="soft-card-copy">
                    一次低分不等于糟糕的一天。记录的目标不是让曲线一直向上，
                    而是更早发现自己需要什么。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    render_summary(entries)
    st.write("")
    render_explore(entries)

    st.divider()
    st.caption(
        "Happy Index 提供个人记录与回顾，不进行心理诊断。"
        "如果低落或痛苦持续影响生活，请向可信任的人或专业人士寻求支持。"
    )


if __name__ == "__main__":
    main()
