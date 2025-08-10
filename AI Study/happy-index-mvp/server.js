const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bodyParser = require('body-parser');
const { v4: uuidv4 } = require('uuid');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(bodyParser.json());
app.use(express.static('.'));

// 数据库初始化
const db = new sqlite3.Database('./mood_community.db', (err) => {
    if (err) {
        console.error('数据库连接失败:', err.message);
    } else {
        console.log('✅ 数据库连接成功');
        initDatabase();
    }
});

// 初始化数据库表
function initDatabase() {
    // 用户表
    db.run(`CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    // 心情记录表
    db.run(`CREATE TABLE IF NOT EXISTS moods (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        score INTEGER NOT NULL,
        text TEXT NOT NULL,
        is_public INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )`);

    // 点赞表
    db.run(`CREATE TABLE IF NOT EXISTS likes (
        id TEXT PRIMARY KEY,
        mood_id TEXT,
        user_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mood_id) REFERENCES moods (id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(mood_id, user_id)
    )`);

    // 评论表
    db.run(`CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        mood_id TEXT,
        user_id TEXT,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mood_id) REFERENCES moods (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )`);

    console.log('✅ 数据库表初始化完成');
}

// API 路由

// 创建或获取用户
app.post('/api/users', (req, res) => {
    const userId = uuidv4();
    
    db.run('INSERT INTO users (id) VALUES (?)', [userId], function(err) {
        if (err) {
            return res.status(500).json({ error: '创建用户失败' });
        }
        res.json({ userId, message: '用户创建成功' });
    });
});

// 提交心情记录
app.post('/api/moods', (req, res) => {
    const { userId, score, text, isPublic } = req.body;
    const moodId = uuidv4();
    
    if (!userId || score === undefined || !text) {
        return res.status(400).json({ error: '缺少必要参数' });
    }
    
    db.run(
        'INSERT INTO moods (id, user_id, score, text, is_public) VALUES (?, ?, ?, ?, ?)',
        [moodId, userId, score, text, isPublic ? 1 : 0],
        function(err) {
            if (err) {
                return res.status(500).json({ error: '保存心情记录失败' });
            }
            res.json({ moodId, message: '心情记录保存成功' });
        }
    );
});

// 获取公开的心情记录（分页）
app.get('/api/moods/public', (req, res) => {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    const offset = (page - 1) * limit;
    
    const query = `
        SELECT 
            m.id,
            m.score,
            m.text,
            m.created_at,
            COUNT(DISTINCT l.id) as like_count,
            COUNT(DISTINCT c.id) as comment_count
        FROM moods m
        LEFT JOIN likes l ON m.id = l.mood_id
        LEFT JOIN comments c ON m.id = c.mood_id
        WHERE m.is_public = 1
        GROUP BY m.id
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
    `;
    
    db.all(query, [limit, offset], (err, rows) => {
        if (err) {
            return res.status(500).json({ error: '获取心情记录失败' });
        }
        res.json(rows);
    });
});

// 获取用户的心情记录
app.get('/api/moods/user/:userId', (req, res) => {
    const { userId } = req.params;
    
    const query = `
        SELECT 
            m.id,
            m.score,
            m.text,
            m.is_public,
            m.created_at,
            COUNT(DISTINCT l.id) as like_count,
            COUNT(DISTINCT c.id) as comment_count
        FROM moods m
        LEFT JOIN likes l ON m.id = l.mood_id
        LEFT JOIN comments c ON m.id = c.mood_id
        WHERE m.user_id = ?
        GROUP BY m.id
        ORDER BY m.created_at DESC
    `;
    
    db.all(query, [userId], (err, rows) => {
        if (err) {
            return res.status(500).json({ error: '获取用户心情记录失败' });
        }
        res.json(rows);
    });
});

// 点赞/取消点赞
app.post('/api/moods/:moodId/like', (req, res) => {
    const { moodId } = req.params;
    const { userId } = req.body;
    
    if (!userId) {
        return res.status(400).json({ error: '缺少用户ID' });
    }
    
    // 检查是否已经点赞
    db.get('SELECT id FROM likes WHERE mood_id = ? AND user_id = ?', [moodId, userId], (err, row) => {
        if (err) {
            return res.status(500).json({ error: '检查点赞状态失败' });
        }
        
        if (row) {
            // 取消点赞
            db.run('DELETE FROM likes WHERE mood_id = ? AND user_id = ?', [moodId, userId], (err) => {
                if (err) {
                    return res.status(500).json({ error: '取消点赞失败' });
                }
                res.json({ liked: false, message: '取消点赞成功' });
            });
        } else {
            // 添加点赞
            const likeId = uuidv4();
            db.run('INSERT INTO likes (id, mood_id, user_id) VALUES (?, ?, ?)', [likeId, moodId, userId], (err) => {
                if (err) {
                    return res.status(500).json({ error: '点赞失败' });
                }
                res.json({ liked: true, message: '点赞成功' });
            });
        }
    });
});

// 添加评论
app.post('/api/moods/:moodId/comments', (req, res) => {
    const { moodId } = req.params;
    const { userId, content } = req.body;
    
    if (!userId || !content) {
        return res.status(400).json({ error: '缺少必要参数' });
    }
    
    const commentId = uuidv4();
    db.run(
        'INSERT INTO comments (id, mood_id, user_id, content) VALUES (?, ?, ?, ?)',
        [commentId, moodId, userId, content],
        function(err) {
            if (err) {
                return res.status(500).json({ error: '添加评论失败' });
            }
            res.json({ commentId, message: '评论添加成功' });
        }
    );
});

// 获取心情记录的评论
app.get('/api/moods/:moodId/comments', (req, res) => {
    const { moodId } = req.params;
    
    db.all(
        'SELECT id, content, created_at FROM comments WHERE mood_id = ? ORDER BY created_at ASC',
        [moodId],
        (err, rows) => {
            if (err) {
                return res.status(500).json({ error: '获取评论失败' });
            }
            res.json(rows);
        }
    );
});

// 获取统计数据
app.get('/api/stats', (req, res) => {
    const queries = {
        totalMoods: 'SELECT COUNT(*) as count FROM moods',
        publicMoods: 'SELECT COUNT(*) as count FROM moods WHERE is_public = 1',
        totalUsers: 'SELECT COUNT(*) as count FROM users',
        avgScore: 'SELECT AVG(score) as avg FROM moods WHERE is_public = 1',
        totalLikes: 'SELECT COUNT(*) as count FROM likes',
        totalComments: 'SELECT COUNT(*) as count FROM comments'
    };
    
    const stats = {};
    let completed = 0;
    const total = Object.keys(queries).length;
    
    Object.entries(queries).forEach(([key, query]) => {
        db.get(query, (err, row) => {
            if (!err) {
                stats[key] = row.count !== undefined ? row.count : row.avg;
            }
            completed++;
            if (completed === total) {
                res.json(stats);
            }
        });
    });
});

// 检查用户是否点赞了某个心情记录
app.get('/api/moods/:moodId/like-status/:userId', (req, res) => {
    const { moodId, userId } = req.params;
    
    db.get('SELECT id FROM likes WHERE mood_id = ? AND user_id = ?', [moodId, userId], (err, row) => {
        if (err) {
            return res.status(500).json({ error: '检查点赞状态失败' });
        }
        res.json({ liked: !!row });
    });
});

// 更新心情记录的隐私设置
app.put('/api/moods/:moodId/privacy', (req, res) => {
    const { moodId } = req.params;
    const { userId, isPublic } = req.body;
    
    db.run(
        'UPDATE moods SET is_public = ? WHERE id = ? AND user_id = ?',
        [isPublic ? 1 : 0, moodId, userId],
        function(err) {
            if (err) {
                return res.status(500).json({ error: '更新隐私设置失败' });
            }
            if (this.changes === 0) {
                return res.status(404).json({ error: '记录不存在或无权限' });
            }
            res.json({ message: '隐私设置更新成功' });
        }
    );
});

// 启动服务器
app.listen(PORT, () => {
    console.log(`🚀 服务器运行在 http://localhost:${PORT}`);
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n正在关闭服务器...');
    db.close((err) => {
        if (err) {
            console.error('关闭数据库连接失败:', err.message);
        } else {
            console.log('✅ 数据库连接已关闭');
        }
        process.exit(0);
    });
});