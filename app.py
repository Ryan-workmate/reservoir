"""
校园活动管理系统 V1.0
基于 Flask + SQLite 的服务端渲染 Web 应用
"""
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# 应用初始化
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'campus-activity-system-v1-secret-key'
app.config['DATABASE'] = os.path.join(app.root_path, 'campus.db')


# ============================================================
# 数据库辅助函数
# ============================================================
def get_db():
    """获取数据库连接，请求内复用"""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """请求结束时关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库表结构"""
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            max_participants INTEGER NOT NULL CHECK(max_participants > 0),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','cancelled')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (activity_id) REFERENCES activities(id),
            UNIQUE(user_id, activity_id)
        );
    ''')
    db.commit()


def query_db(query, args=(), one=False):
    """查询辅助函数，返回字典列表或单个字典"""
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    """执行写操作（INSERT/UPDATE/DELETE），返回 lastrowid"""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def get_activity_with_count(activity_id):
    """获取活动详情及已报名人数"""
    activity = query_db('''
        SELECT a.*, u.username as teacher_name,
               (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) as registered_count
        FROM activities a
        JOIN users u ON a.teacher_id = u.id
        WHERE a.id = ?
    ''', (activity_id,), one=True)
    return activity


# ============================================================
# 登录/权限装饰器
# ============================================================
def login_required(f):
    """要求用户已登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def teacher_required(f):
    """要求用户是教师角色"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            flash('该功能仅教师可用', 'danger')
            return redirect(url_for('activity_list'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """要求用户是学生角色"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('该功能仅学生可用', 'danger')
            return redirect(url_for('activity_list'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# 模板上下文：注入当前用户信息
# ============================================================
@app.context_processor
def inject_user():
    return {
        'current_user_id': session.get('user_id'),
        'current_username': session.get('username'),
        'current_role': session.get('role'),
    }


# ============================================================
# 认证模块：注册、登录、登出
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册（REQ-01）"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '')

        # 表单校验
        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return render_template('register.html')
        if len(username) < 2:
            flash('用户名至少2个字符', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('密码至少6个字符', 'danger')
            return render_template('register.html')
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('register.html')
        if role not in ('student', 'teacher'):
            flash('请选择用户角色', 'danger')
            return render_template('register.html')

        # 检查用户名是否已存在
        existing = query_db('SELECT id FROM users WHERE username = ?', (username,), one=True)
        if existing:
            flash('该用户名已被注册', 'danger')
            return render_template('register.html')

        # 创建用户（密码哈希存储）
        password_hash = generate_password_hash(password)
        execute_db(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (username, password_hash, role)
        )
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录（REQ-02）"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return render_template('login.html')

        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user is None or not check_password_hash(user['password_hash'], password):
            flash('用户名或密码错误', 'danger')
            return render_template('login.html')

        # 登录成功，写入 session
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

        flash(f'欢迎回来，{user["username"]}', 'success')
        return redirect(url_for('activity_list'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


# ============================================================
# 活动模块：列表、详情、发布、取消
# ============================================================
@app.route('/')
@app.route('/activities')
@login_required
def activity_list():
    """活动列表（REQ-03）"""
    status_filter = request.args.get('status', 'all')

    if status_filter == 'open':
        activities = query_db('''
            SELECT a.*, u.username as teacher_name,
                   (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) as registered_count
            FROM activities a
            JOIN users u ON a.teacher_id = u.id
            WHERE a.status = 'open'
            ORDER BY a.created_at DESC
        ''')
    elif status_filter == 'cancelled':
        activities = query_db('''
            SELECT a.*, u.username as teacher_name,
                   (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) as registered_count
            FROM activities a
            JOIN users u ON a.teacher_id = u.id
            WHERE a.status = 'cancelled'
            ORDER BY a.created_at DESC
        ''')
    else:
        activities = query_db('''
            SELECT a.*, u.username as teacher_name,
                   (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) as registered_count
            FROM activities a
            JOIN users u ON a.teacher_id = u.id
            ORDER BY a.created_at DESC
        ''')

    return render_template('activity_list.html', activities=activities, status_filter=status_filter)


@app.route('/activities/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    """活动详情（REQ-03）"""
    activity = get_activity_with_count(activity_id)
    if activity is None:
        abort(404)

    # 检查当前用户是否已报名
    is_registered = False
    if session.get('role') == 'student':
        reg = query_db(
            'SELECT id FROM registrations WHERE user_id = ? AND activity_id = ?',
            (session['user_id'], activity_id), one=True
        )
        is_registered = reg is not None

    return render_template('activity_detail.html', activity=activity, is_registered=is_registered)


@app.route('/activities/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_activity():
    """发布活动（REQ-07）"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        start_time = request.form.get('start_time', '')
        max_participants = request.form.get('max_participants', '')

        # 表单校验
        if not all([title, description, location, start_time, max_participants]):
            flash('所有字段均为必填', 'danger')
            return render_template('create_activity.html')

        try:
            max_participants = int(max_participants)
            if max_participants <= 0:
                raise ValueError
        except ValueError:
            flash('最大报名人数必须是正整数', 'danger')
            return render_template('create_activity.html')

        # 校验时间格式
        try:
            datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('活动时间格式不正确', 'danger')
            return render_template('create_activity.html')

        # 创建活动
        activity_id = execute_db('''
            INSERT INTO activities (teacher_id, title, description, location, start_time, max_participants)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, description, location, start_time, max_participants))

        flash('活动发布成功', 'success')
        return redirect(url_for('activity_manage', activity_id=activity_id))

    return render_template('create_activity.html')


@app.route('/activities/<int:activity_id>/manage')
@login_required
@teacher_required
def activity_manage(activity_id):
    """活动管理页：查看报名名单（REQ-08）"""
    activity = get_activity_with_count(activity_id)
    if activity is None:
        abort(404)

    # 只能管理自己发布的活动
    if activity['teacher_id'] != session['user_id']:
        flash('您只能管理自己发布的活动', 'danger')
        return redirect(url_for('my_activities'))

    # 获取报名学生名单
    registrations = query_db('''
        SELECT r.id, r.created_at, u.username, u.id as user_id
        FROM registrations r
        JOIN users u ON r.user_id = u.id
        WHERE r.activity_id = ?
        ORDER BY r.created_at ASC
    ''', (activity_id,))

    return render_template('activity_manage.html', activity=activity, registrations=registrations)


@app.route('/activities/<int:activity_id>/cancel', methods=['POST'])
@login_required
@teacher_required
def cancel_activity(activity_id):
    """取消活动（REQ-09）"""
    activity = query_db('SELECT * FROM activities WHERE id = ?', (activity_id,), one=True)
    if activity is None:
        abort(404)

    # 只能取消自己发布的活动
    if activity['teacher_id'] != session['user_id']:
        flash('您只能取消自己发布的活动', 'danger')
        return redirect(url_for('my_activities'))

    if activity['status'] == 'cancelled':
        flash('该活动已取消', 'warning')
        return redirect(url_for('activity_manage', activity_id=activity_id))

    execute_db('UPDATE activities SET status = ? WHERE id = ?', ('cancelled', activity_id))
    flash('活动已取消', 'success')
    return redirect(url_for('activity_manage', activity_id=activity_id))


@app.route('/my-activities')
@login_required
@teacher_required
def my_activities():
    """教师：我的活动列表（REQ-08）"""
    activities = query_db('''
        SELECT a.*,
               (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) as registered_count
        FROM activities a
        WHERE a.teacher_id = ?
        ORDER BY a.created_at DESC
    ''', (session['user_id'],))

    return render_template('my_activities.html', activities=activities)


# ============================================================
# 报名模块：报名、取消报名、我的报名
# ============================================================
@app.route('/activities/<int:activity_id>/register', methods=['POST'])
@login_required
@student_required
def register_activity(activity_id):
    """学生报名活动（REQ-04）"""
    activity = get_activity_with_count(activity_id)
    if activity is None:
        abort(404)

    # 校验1：活动状态必须是报名中
    if activity['status'] == 'cancelled':
        flash('该活动已取消，无法报名', 'danger')
        return redirect(url_for('activity_detail', activity_id=activity_id))

    # 校验2：不能重复报名
    existing = query_db(
        'SELECT id FROM registrations WHERE user_id = ? AND activity_id = ?',
        (session['user_id'], activity_id), one=True
    )
    if existing:
        flash('您已报名该活动，无需重复报名', 'warning')
        return redirect(url_for('activity_detail', activity_id=activity_id))

    # 校验3：名额是否已满
    if activity['registered_count'] >= activity['max_participants']:
        flash('该活动报名名额已满', 'danger')
        return redirect(url_for('activity_detail', activity_id=activity_id))

    # 创建报名记录
    execute_db(
        'INSERT INTO registrations (user_id, activity_id) VALUES (?, ?)',
        (session['user_id'], activity_id)
    )
    flash('报名成功', 'success')
    return redirect(url_for('activity_detail', activity_id=activity_id))


@app.route('/activities/<int:activity_id>/cancel-registration', methods=['POST'])
@login_required
@student_required
def cancel_registration(activity_id):
    """学生取消报名（REQ-05）"""
    activity = query_db('SELECT * FROM activities WHERE id = ?', (activity_id,), one=True)
    if activity is None:
        abort(404)

    # 检查是否有报名记录（只能取消自己的）
    reg = query_db(
        'SELECT id FROM registrations WHERE user_id = ? AND activity_id = ?',
        (session['user_id'], activity_id), one=True
    )
    if reg is None:
        flash('您未报名该活动', 'warning')
        return redirect(url_for('activity_detail', activity_id=activity_id))

    # 删除报名记录（取消报名 = 删除记录，释放名额）
    execute_db(
        'DELETE FROM registrations WHERE user_id = ? AND activity_id = ?',
        (session['user_id'], activity_id)
    )
    flash('已取消报名', 'success')
    return redirect(url_for('activity_detail', activity_id=activity_id))


@app.route('/my-registrations')
@login_required
@student_required
def my_registrations():
    """学生：我的报名列表（REQ-06）"""
    registrations = query_db('''
        SELECT r.id as reg_id, r.created_at as reg_time,
               a.id as activity_id, a.title, a.description, a.location,
               a.start_time, a.status, a.max_participants,
               (SELECT COUNT(*) FROM registrations r2 WHERE r2.activity_id = a.id) as registered_count
        FROM registrations r
        JOIN activities a ON r.activity_id = a.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    ''', (session['user_id'],))

    return render_template('my_registrations.html', registrations=registrations)


# ============================================================
# 错误处理
# ============================================================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ============================================================
# 应用入口
# ============================================================
if __name__ == '__main__':
    with app.app_context():
        init_db()
        print('数据库初始化完成')
    print('校园活动管理系统 V1.0 启动中...')
    print('访问地址: http://127.0.0.1:5000')
    app.run(debug=True)
