from flask import Flask
from threading import Thread
import requests
import time
import os

app = Flask('')

@app.route('/')
def home():
    return "Discord Bot is alive and running!"

@app.route('/health')
def health():
    return {"status": "healthy", "message": "Bot is running"}

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def ping_self():
    """자기 자신을 주기적으로 핑하여 슬립 방지"""
    while True:
        try:
            # 14분마다 자기 자신에게 요청
            time.sleep(840)  # 14분 = 840초
            url = os.environ.get('RENDER_EXTERNAL_URL')
            if url:
                requests.get(f"{url}/health", timeout=10)
                print("Self-ping successful")
        except Exception as e:
            print(f"Self-ping failed: {e}")

def start_ping():
    ping_thread = Thread(target=ping_self)
    ping_thread.daemon = True
    ping_thread.start()