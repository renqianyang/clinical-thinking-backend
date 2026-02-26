# Clinical Thinking Training System - Backend

## 部署到 Render

### 方法1：一键部署（推荐）

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### 方法2：手动部署

1. 在 [render.com](https://render.com) 注册账号
2. 创建新的 Web Service
3. 连接你的 GitHub/GitLab 仓库，或上传代码
4. 配置：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 点击部署

### 环境变量（可选）

在 Render Dashboard 中设置：
- `SECRET_KEY` - JWT 密钥（生产环境必须修改）
- `DATABASE_URL` - 数据库 URL（默认 SQLite）

## 本地运行

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API 文档

部署后访问：`https://your-service-name.onrender.com/docs`

## 默认账号

- 教师：`teacher` / `teacher123`
- 学生：`student` / `student123`
