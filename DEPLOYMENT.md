# Deployment Guide

This guide covers deploying the Collaborative Editing System with:
- **Backend**: Heroku (Python/FastAPI)
- **Frontend**: Vercel (React)

## Prerequisites

- Heroku CLI installed (`brew install heroku/brew/heroku`)
- Vercel CLI installed (`npm i -g vercel`)
- Git installed

## Backend Deployment (Heroku)

### 1. Create Heroku App

```bash
# Login to Heroku
heroku login

# Create a new app
heroku create your-app-name

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:essential-0
```

### 2. Configure Environment Variables

```bash
# Set secret key for JWT
heroku config:set SECRET_KEY="your-super-secret-key-change-this"

# Set allowed origins for CORS (your Vercel frontend URL)
heroku config:set ALLOWED_ORIGINS="https://your-frontend.vercel.app"
```

### 3. Deploy

```bash
# Push to Heroku (from the root directory)
git push heroku main
```

### 4. Verify

```bash
# Check logs
heroku logs --tail

# Open the app
heroku open
```

## Frontend Deployment (Vercel)

### 1. Configure Environment Variables

In the Vercel dashboard or CLI, set these environment variables:

| Variable | Value |
|----------|-------|
| `REACT_APP_API_URL` | `https://your-heroku-app.herokuapp.com/api` |
| `REACT_APP_WS_URL` | `wss://your-heroku-app.herokuapp.com` |

### 2. Deploy with Vercel CLI

```bash
# Navigate to frontend directory
cd frontend

# Login to Vercel
vercel login

# Deploy (follow prompts)
vercel

# For production deployment
vercel --prod
```

### 3. Deploy via Git (Recommended)

1. Connect your GitHub repo to Vercel
2. Set the root directory to `frontend`
3. Add environment variables in Vercel dashboard
4. Deploy automatically on push

## Environment Variables Summary

### Backend (Heroku)

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-set by Heroku |
| `SECRET_KEY` | JWT signing key | Yes |
| `ALLOWED_ORIGINS` | CORS allowed origins | Yes |

### Frontend (Vercel)

| Variable | Description | Required |
|----------|-------------|----------|
| `REACT_APP_API_URL` | Backend API URL | Yes |
| `REACT_APP_WS_URL` | Backend WebSocket URL | Yes |

## Updating CORS Settings

Update `main.py` to use environment variable for CORS:

```python
import os

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Troubleshooting

### WebSocket Connection Issues

1. Ensure `REACT_APP_WS_URL` uses `wss://` (secure WebSocket)
2. Check Heroku logs for connection errors
3. Verify CORS settings include your frontend domain

### Database Issues

1. Check PostgreSQL addon is provisioned: `heroku addons`
2. View database URL: `heroku config:get DATABASE_URL`
3. Run migrations if needed (tables are auto-created on startup)

### Build Failures

- Heroku: Check `requirements.txt` for invalid packages
- Vercel: Check `package.json` and Node version
