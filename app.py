import json
import os
import io
import zipfile
import time
from flask import Flask, render_template, request, jsonify, send_file
import requests

app = Flask(__name__)

CONFIG_FILE = 'config.json'
USER_FILE = 'user.json'
VERILER_FILE = 'veriler.json'

FREE_MODELS = [
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nvidia Nemotron 3 Ultra (550B - En Güçlü)"},
    {"id": "google/gemma-4-31b-it:free", "name": "Google Gemma 4 (31B IT)"},
    {"id": "google/gemma-4-26b-a4b-it:free", "name": "Google Gemma 4 (26B IT)"},
    {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "name": "Nemotron 3 Nano Omni (Reasoning)"},
    {"id": "nvidia/nemotron-3.5-super-vl:free", "name": "Nemotron 3.5 Super VL (Görsel Destekli)"},
    {"id": "cohere/north-mini-code:free", "name": "Cohere North Mini (Kod Uzmanı)"},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning (Ultra Hızlı)"},
    {"id": "inclusionai/ling-3.2-flash:free", "name": "Ling 3.2 Flash"},
    {"id": "baidu/ernie-5.5-flash-preview:free", "name": "Baidu Ernie 5.5 Flash"},
    {"id": "recursive/flint-v1.0:free", "name": "Flint v1.0"},
    {"id": "thinkingmachines/inkling-2-small:free", "name": "Inkling 2 Small"},
    {"id": "liquid/lfm-3-1.7b:free", "name": "Liquid LFM 3 (1.7B - Hafif)"},
    {"id": "particle-ai/particle-1:free", "name": "Particle 1"},
    {"id": "dots-studio/dots-3-note-preview:free", "name": "Dots 3 Note Preview"}
]

def load_json(filename, default_data):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=4)
        return default_data
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default_data

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    config = load_json(CONFIG_FILE, {})
    user = load_json(USER_FILE, {})
    is_setup = bool(config.get("openrouter_api_key") and user.get("name"))
    return render_template('index.html', user=user, config=config, is_setup=is_setup, models=FREE_MODELS)

@app.route('/api/setup', methods=['POST'])
def setup():
    data = request.get_json()
    name = data.get('name', '').strip()
    age = data.get('age', 14)
    api_key = data.get('api_key', '').strip()
    model = data.get('model', 'nvidia/nemotron-3-ultra-550b-a55b:free')

    if not name or not api_key:
        return jsonify({"error": "İsim ve API Key alanları zorunludur!"}), 400

    config = load_json(CONFIG_FILE, {})
    config["openrouter_api_key"] = api_key
    config["model"] = model
    save_json(CONFIG_FILE, config)

    user = load_json(USER_FILE, {})
    user["name"] = name
    user["age"] = int(age)
    save_json(USER_FILE, user)

    return jsonify({"success": True})

@app.route('/api/data', methods=['GET'])
def get_data():
    veriler = load_json(VERILER_FILE, {"current_session_id": "default", "sessions": {"default": {"title": "Yeni Sohbet", "pinned": False, "chats": []}}})
    user = load_json(USER_FILE, {})
    config = load_json(CONFIG_FILE, {})
    return jsonify({
        "veriler": veriler,
        "user": user,
        "model": config.get("model", "nvidia/nemotron-3-ultra-550b-a55b:free")
    })

@app.route('/api/sessions/new', methods=['POST'])
def new_session():
    veriler = load_json(VERILER_FILE, {"current_session_id": "default", "sessions": {}})
    session_id = f"chat_{int(time.time())}"
    veriler["sessions"][session_id] = {
        "title": "Yeni Sohbet",
        "pinned": False,
        "chats": []
    }
    veriler["current_session_id"] = session_id
    save_json(VERILER_FILE, veriler)
    return jsonify({"success": True, "session_id": session_id, "veriler": veriler})

@app.route('/api/sessions/switch', methods=['POST'])
def switch_session():
    data = request.get_json()
    session_id = data.get('session_id')
    veriler = load_json(VERILER_FILE, {})
    if session_id in veriler.get("sessions", {}):
        veriler["current_session_id"] = session_id
        save_json(VERILER_FILE, veriler)
        return jsonify({"success": True, "veriler": veriler})
    return jsonify({"error": "Oturum bulunamadı."}), 404

@app.route('/api/sessions/pin', methods=['POST'])
def pin_session():
    data = request.get_json()
    session_id = data.get('session_id')
    veriler = load_json(VERILER_FILE, {})
    if session_id in veriler.get("sessions", {}):
        current_pin = veriler["sessions"][session_id].get("pinned", False)
        veriler["sessions"][session_id]["pinned"] = not current_pin
        save_json(VERILER_FILE, veriler)
        return jsonify({"success": True, "veriler": veriler})
    return jsonify({"error": "Oturum bulunamadı."}), 404

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    image_data = data.get('image', None) # Base64 görsel
    
    if not user_message and not image_data:
        return jsonify({"error": "Boş mesaj gönderilemez."}), 400

    config = load_json(CONFIG_FILE, {})
    user_info = load_json(USER_FILE, {})
    veriler = load_json(VERILER_FILE, {"current_session_id": "default", "sessions": {"default": {"title": "Yeni Sohbet", "pinned": False, "chats": []}}})

    current_id = veriler.get("current_session_id", "default")
    if current_id not in veriler["sessions"]:
        current_id = "default"
        veriler["current_session_id"] = current_id

    current_session = veriler["sessions"][current_id]

    # İlk mesajda akıllı başlık belirleme (İlk 4-5 kelime veya konuya göre özet)
    if len(current_session["chats"]) == 0:
        words = user_message.split()
        smart_title = " ".join(words[:4]) if words else "Kod Analizi"
        if len(smart_title) > 28:
            smart_title = smart_title[:25] + "..."
        current_session["title"] = smart_title

    api_key = config.get("openrouter_api_key")
    model = config.get("model", "nvidia/nemotron-3-ultra-550b-a55b:free")

    if not api_key:
        return jsonify({"error": "API anahtarı bulunamadı. Lütfen ayarları yapın."}), 400

    system_prompt = f"{user_info.get('system_prompt', '')} Kullanıcının adı: {user_info.get('name', 'Kullanıcı')}, Yaşı: {user_info.get('age', 14)}."
    
    messages = [{"role": "system", "content": system_prompt}]
    
    for chat_item in current_session["chats"][-15:]:
        messages.append({"role": "user", "content": chat_item.get("user")})
        messages.append({"role": "assistant", "content": chat_item.get("assistant")})

    # Multimodal veya normal mesaj payload hazırlığı
    if image_data:
        content_payload = [
            {"type": "text", "text": user_message if user_message else "Bu görseli analiz et ve açıkla."},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]
        messages.append({"role": "user", "content": content_payload})
    else:
        messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.get("site_url", "http://localhost:5000"),
        "X-Title": config.get("site_name", "Pydroid AI Studio")
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        res_json = response.json()
        
        if response.status_code != 200:
            error_msg = res_json.get("error", {}).get("message", "OpenRouter API Hatası")
            return jsonify({"error": error_msg}), 400

        ai_reply = res_json["choices"][0]["message"]["content"]

        current_session["chats"].append({"user": user_message + (" [Görsel Eklendi]" if image_data else ""), "assistant": ai_reply})
        save_json(VERILER_FILE, veriler)

        return jsonify({"reply": ai_reply, "veriler": veriler})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-zip', methods=['POST'])
def download_zip():
    data = request.get_json()
    code_snippets = data.get('snippets', [])

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if code_snippets:
            for idx, snippet in enumerate(code_snippets):
                filename = snippet.get('filename', f'kod_{idx+1}.txt')
                content = snippet.get('content', '')
                zf.writestr(filename, content)
        else:
            veriler = load_json(VERILER_FILE, {})
            zf.writestr('sohbet_gecmisi.json', json.dumps(veriler, ensure_ascii=False, indent=4))
            zf.writestr('user.json', json.dumps(load_json(USER_FILE, {}), ensure_ascii=False, indent=4))

    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name='ai_proje_dosyalari.zip')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
