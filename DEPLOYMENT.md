# Deployment Guide - Render

## Prerequisites
- GitHub/GitLab account
- Public repository with your code

## Quick Deploy to Render

### Step 1: Push Code to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
# Create a GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/chat-app.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to https://dashboard.render.com
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: chat-app
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 8000`
   - **Branch**: main
5. Click "Deploy Web Service"

### Step 3: Environment Variables

In Render dashboard, go to Environment tab and add:
- `PYTHON_VERSION`: 3.11

### Step 4: Wait for Deploy

The deploy will complete in 2-3 minutes. Your app will be available at:
`https://your-app-name.onrender.com`

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
cd backend
python main.py
# or
uvicorn main:app --reload
```

## Testing

1. Open your Render URL in 3 different browser tabs
2. Enter different usernames in each
3. Test sending messages between them
4. Test leaving/rejoining
5. Verify messages persist after refresh

## Troubleshooting

- **WebSocket errors**: Check Render logs for errors
- **Static files not loading**: Ensure frontend folder is alongside backend
- **Database errors**: SQLite works on Render within the filesystem

## Production Notes

- Free tier: service sleeps after 15 min of inactivity
- To keep 24/7, add a ping service or upgrade to paid tier
- For production, consider PostgreSQL (Render provides free tier)