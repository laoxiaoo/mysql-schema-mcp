# 介绍

连接数据库获取表结构的mcp

# 将 MySQL Schema MCP 配置到 Codex 和 Claude Code

  ## 1. 先准备 MCP 项目

  项目目录是：

  /home/user/gitcode/mysql-schema-mcp

  初始化依赖和配置：

  cd /home/user/gitcode/mysql-schema-mcp
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cp mysql.ini.example mysql.ini

  然后编辑：

  vim mysql.ini

  填入你的 MySQL 信息。注意 mysql.ini 里配置的 database 就是 get_table_schema
  查询的库。

  ## 2. 配置到 Codex

  Codex 官方配置位置是 ~/.codex/config.toml，MCP server 写在
  [mcp_servers.<name>] 下。

  追加下面这段：

```toml

[mcp_servers.mysql-schema]
command = "/home/user/gitcode/mysql-schema-mcp/.venv/bin/python"
args = ["/home/user/gitcode/mysql-schema-mcp/server.py"]
cwd = "/home/user/gitcode/mysql-schema-mcp"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 60
enabled_tools = ["get_table_schema"]


```

  验证：

  codex mcp list
  codex mcp get mysql-schema

  然后重启 Codex 会话，在 Codex 里执行 /mcp 看是否出现 mysql-schema。

  ## 3. 配置到 Claude Code

  推荐用 Claude Code 命令添加到 user scope，这样所有项目都能用：

```shell

claude mcp add --transport stdio --scope user mysql-schema -- /home/user/gitcode/mysql-schema-mcp/.venv/bin/python /home/user/gitcode/mysql-schema-mcp/server.py

```

  验证：

  claude mcp list
  claude mcp get mysql-schema

  进入 Claude Code 后也可以输入：

  /mcp

  确认 mysql-schema 已连接。

  ## 4. 使用方式

  在 Codex 或 Claude Code 里直接问类似：

  调用 mysql-schema 的 get_table_schema，查看 pur_order 表结构

  或：

  使用 get_table_schema 查询 table_name=pur_order

  ## 5. 常见问题

  - 如果提示找不到 mcp 或 pymysql，说明虚拟环境没装依赖，重新执行 pip install
    -r requirements.txt。
  - 如果连接失败，检查 mysql.ini 的 host、port、user、password、database。
  - 如果工具不出现，优先检查 Python 路径是否是绝对路径：/home/user/gitcode/
    mysql-schema-mcp/.venv/bin/python。
  - 如果 Claude Code 项目级共享配置才是你要的，可以改用 .mcp.json；但你的这个
    MCP 含本机路径和数据库配置，默认更适合 user scope。

  参考官方文档：

  - Codex MCP 配置：https://www.mintlify.com/openai/codex/configuration/mcp-
    servers
  - Claude Code MCP 配置：https://code.claude.com/docs/en/mcp
