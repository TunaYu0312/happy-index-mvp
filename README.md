# Happy Index 心情指数

一个轻量、克制的每日心情记录应用。用约一分钟记录 1–10 分的主观心情、最接近的感受和一句话备注，再通过 7/30/90 天趋势温和地回看变化。

> Happy Index 用于个人记录与反思，不进行心理诊断，也不能替代专业心理支持。

## 这次升级解决了什么

首版 MVP 已经具备数据库写入和基础图表，但交互更接近“表单 + 报表”。新版把使用路径收敛为：

```text
选择个人昵称
→ 记录此刻
→ 确认今天状态
→ 查看趋势与温和提示
→ 导出自己的记录
```

主要变化：

- 重新设计响应式页面、视觉层级和移动端布局
- 以“今天是否已记录”为核心状态，而不是先展示统计报表
- Demo 模式支持本次浏览会话内真实提交，不再是无反馈表单
- 数据库查询按昵称过滤，界面不再加载和展示所有人的记录
- 增加连续记录天数、近 7 天相对前 7 天变化
- 合并 7/30/90 天周期选择，减少重复标签页
- 增加 CSV 导出
- 对数据库错误使用安全提示，不向页面泄露连接细节
- 把数据处理逻辑拆分到 `mood_logic.py`，并增加单元测试

## 项目结构

```text
.
├── .streamlit/
│   └── config.toml
├── tests/
│   └── test_mood_logic.py
├── mood_logic.py
├── streamlit_app.py
├── requirements.txt
└── README.md
```

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

未配置数据库时，应用自动进入 Demo 模式。`demo_user` 会看到 30 天示例数据，任何昵称都可以在当前浏览会话中提交记录；这些新记录不会长期保存。

## 运行测试

```powershell
python -m unittest discover -s tests -v
```

## 配置 Streamlit Secrets

数据库配置通过 Streamlit 的 `st.secrets` 读取，不要把密码或 API Key 写进代码。

本地开发时，创建 `.streamlit/secrets.toml`：

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

`.streamlit/secrets.toml` 已加入 `.gitignore`。

## 数据库表结构

新版继续兼容首版 PostgreSQL/Supabase 表，不需要迁移：

```sql
create table if not exists public.happy_index_entries (
    id bigserial primary key,
    created_at timestamptz not null default now(),
    user_name text not null,
    mood_score integer not null check (mood_score between 1 and 10),
    mood_label text not null,
    note text
);

create index if not exists idx_happy_index_entries_created_at
    on public.happy_index_entries (created_at desc);

create index if not exists idx_happy_index_entries_user_name
    on public.happy_index_entries (lower(trim(user_name)));
```

## 部署到 Streamlit Community Cloud

1. 在 Streamlit Community Cloud 新建应用。
2. 选择该 GitHub 仓库和准备部署的分支。
3. 入口文件选择 `streamlit_app.py`。
4. 建议使用 Python 3.12。
5. 在 App Settings 中填入数据库 Secrets。

如果 Secrets 未配置或数据库暂时不可用，应用会进入 Demo 模式。

## 已知边界

- 当前 MVP 使用昵称查找记录，昵称不是可靠的身份验证。
- 在面向公众保存真实情绪数据前，必须增加登录、行级数据权限、删除与账户注销能力。
- 当前允许一天记录多次，并以当天平均值绘制趋势。
- 规则化提示只描述数据变化，不推断心理状态。

## 下一阶段

P1 建议优先级：

1. 增加账号登录和 Supabase Row Level Security。
2. 支持编辑或删除本人记录。
3. 增加“影响因素”结构化标签，但避免过度量化。
4. 增加每周回顾，不做自动心理诊断。
