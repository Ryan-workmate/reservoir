# 校园活动管理系统 V1.0

基于 Flask + SQLite 的校园活动管理系统，支持学生浏览报名活动、教师发布管理活动。

## 功能特性

- 用户注册/登录（学生、教师两种角色）
- 活动发布与管理（教师）
- 活动浏览与详情查看
- 活动报名与取消（学生）
- 报名名单查看（教师）
- 活动取消（教师）

## 技术栈

- Python 3.x
- Flask 3.0
- SQLite
- Jinja2 模板
- 原生 CSS

## 快速开始

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 启动系统

```bash
python app.py
```

### 3. 访问

浏览器打开 http://127.0.0.1:5000

## 项目结构

```
campus-activity-system/
├── app.py              # 主程序（路由、业务逻辑、数据库）
├── requirements.txt    # 依赖清单
├── README.md           # 项目说明
├── .gitignore          # Git忽略文件
├── templates/          # HTML模板
│   ├── base.html       # 基础布局
│   ├── login.html      # 登录页
│   ├── register.html   # 注册页
│   ├── activity_list.html    # 活动列表
│   ├── activity_detail.html   # 活动详情
│   ├── my_registrations.html  # 我的报名
│   ├── create_activity.html    # 发布活动
│   ├── my_activities.html      # 我的活动
│   └── activity_manage.html    # 活动管理
├── static/
│   └── css/style.css   # 样式文件
└── docs/               # 项目文档
    ├── 01-需求分析.md
    ├── 02-工程意图.md
    └── 03-软件设计.md
```

## 使用说明

1. 注册账号时选择角色（学生/教师）
2. 学生登录后可浏览活动、报名/取消报名、查看我的报名
3. 教师登录后可发布活动、查看我的活动、查看报名名单、取消活动
4. 活动取消后学生不能再报名
