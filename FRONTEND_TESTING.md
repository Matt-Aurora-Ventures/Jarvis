# Jarvis Frontend - Testing Guide

## 🚀 Quick Start

### 1. Install Frontend Dependencies
```bash
cd frontend
npm install
```

### 2. Start API Backend
```bash
# Terminal 1
cd ..
python3 api/server.py
```

### 3. Start Frontend Dev Server
```bash
# Terminal 2
cd frontend
npm run dev
```

### 4. Open Browser
Navigate to: `http://localhost:5173`

---

## 📊 Features to Test

### ✅ Dashboard (/)
- View system stats (active time, tasks, suggestions, focus score)
- Monitor current activity
- Check system component status
- Review recent suggestions

###  🎤 Voice Control (/voice)
- Toggle voice on/off
- Select TTS engine (say, openai_tts, piper)
- Choose voice (Samantha, Nova, etc.)
- Monitor real-time costs
- Test voice output
- Enable/disable barge-in

### 📈 Trading (/trading)
- View trading statistics
- Scan Solana tokens (top 50 high-volume)
- Run 90-day backtests
- Monitor backtest results
- View token table with volumes/prices

### 💬 Chat (/chat)
- Text-based chat with Jarvis
- View conversation history

### ⚙️ Settings (/settings)
- Configure system settings

---

## 🧪 API Endpoints

The Flask backend (`api/server.py`) provides:

```
GET  /api/stats                      - Dashboard stats
GET  /api/voice/status               - Voice system status
POST /api/voice/config               - Update voice config
POST /api/voice/test                 - Test voice output
GET  /api/costs/tts                  - TTS cost monitoring
GET  /api/trading/stats              - Trading statistics
GET  /api/trading/solana/tokens      - Solana token list
POST /api/trading/solana/scan        - Trigger scan
GET  /api/trading/backtests          - Backtest results
POST /api/trading/backtests/run      - Run backtests
```

---

## 🎨 Design Features

- **Dark Mode**: Sleek dark theme with glassmorphism
- **Real-time Updates**: Auto-refresh every 2-5 seconds
- **Responsive**: Works on desktop and mobile
- **Animated**: Smooth transitions and loading states
- **Interactive**: Click actions trigger real backend operations

---

## 🧰 Tech Stack

**Frontend:**
- React 18
- React Router
- Tailwind CSS
- Lucide Icons
- Vite

**Backend:**
- Flask
- Flask-CORS
- Python 3.9+

**Integration:**
- Connects to existing Jarvis core modules
- Real Solana scanner data
- Real backtest results
- Live cost monitoring

---

## 🐛 Troubleshooting

**Port Already in Use:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173
lsof -ti:5173 | xargs kill -9
```

**Flask Not Found:**
```bash
pip install flask flask-cors
```

**Missing Dependencies:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## ✅ Test Checklist

- [ ] Frontend loads at localhost:5173
- [ ] API responds at localhost:8000
- [ ] Dashboard shows stats
- [ ] Voice Control page loads
- [ ] Trading page loads
- [ ] Can scan Solana tokens
- [ ] Can run backtests
- [ ] Cost monitor shows data
- [ ] Navigation works between all pages
- [ ] Voice test button works

---

##  🎯 Next Steps

1. Test all frontend pages
2. Verify API integration
3. Check real-time updates
4. Test voice controls
5. Run trading scans
6. Monitor costs

**All features are live and ready to test!** 🚀
