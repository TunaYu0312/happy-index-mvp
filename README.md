# Happy Index 心情指数

一个可部署到 Streamlit Community Cloud 的心情记录 MVP。用户可以每天记录昵称、心情分数、心情标签和一句话备注，并查看最近记录、7 天/30 天趋势、心情标签分布和简单洞察。

## 本地运行

1. 创建并进入虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 启动应用：

```powershell
streamlit run streamlit_app.py
```

如果没有配置数据库，应用会自动进入 demo 模式，使用本地示例数据展示，并在页面明确标注为 demo 模式。demo 模式下提交不会写入持久化数据库。

## 配置 Streamlit Secrets

本项目不在代码中保存数据库密码或 API key。数据库配置通过 Streamlit 的 `st.secrets` 读取。

本地开发时，可以创建 `.streamlit/secrets.toml`：

```toml
[database]
url = "postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres"
sslmode = "require"
```

也可以使用拆分字段：

```toml
[database]
host = "YOUR_HOST"
port = 5432
dbname = "postgres"
user = "postgres"
password = "YOUR_PASSWORD"
sslmode = "require"
```

`.streamlit/secrets.toml` 已加入 `.gitignore`，不要提交到 GitHub。

## 部署到 Streamlit Community Cloud

1. 将本项目推送到 GitHub 仓库。
2. 登录 [Streamlit Community Cloud](https://streamlit.io/cloud)。
3. 选择 `New app`。
4. 选择对应 GitHub 仓库、分支和入口文件：

```text
streamlit_app.py
```

5. 在 Streamlit Cloud 的 app settings 中配置 Secrets，内容参考上面的 `[database]` 配置。
6. 部署后打开应用。如果 Secrets 未配置或配置不完整，应用会以 demo 模式运行。

## 数据库表结构

优先支持 Supabase/PostgreSQL。可以在 Supabase SQL Editor 或 PostgreSQL 客户端执行：

```sql
create table if not exists public happy_index_entries (
    id bigserial primary key,
    created_at timestamptz not null default now(),
    user_name text not null,
    mood_score integer not null check (mood_score between 1 and 10),
    mood_label text not null,
    note text
);

create index if not exists idx_happy_index_entries_created_at
    on public happy_index_entries (created_at desc);

create index if not exists idx_happy_index_entries_mood_label
    on public happy_index_entries (mood_label);
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `bigserial` | 主键 |
| `created_at` | `timestamptz` | 记录创建时间，默认数据库当前时间 |
| `user_name` | `text` | 用户昵称 |
| `mood_score` | `integer` | 心情分数，1-10 |
| `mood_label` | `text` | 心情标签，例如开心、平静、焦虑、疲惫、低落、兴奋 |
| `note` | `text` | 一句话备注 |

## 功能清单

- 首页标题：`Happy Index 心情指数`
- 每日心情记录表单
- PostgreSQL/Supabase 持久化写入
- 无数据库配置时自动进入 demo 模式
- 最近 30 条心情记录
- 最近 7 天/30 天平均心情趋势图
- 不同心情标签分布图
- 简单洞察区：当前平均心情分、最近一次记录、最常见心情标签、本周最低心情日期
