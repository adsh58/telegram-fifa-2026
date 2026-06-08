import os
import sys
import json
import base64
import re
import requests

PROMPT = (
    "You are a professional sports journalist and social media manager specializing in international soccer/football.\n"
    "Search for the latest news, updates, announcements, or key details about the upcoming FIFA World Cup 2026 (such as qualifier results, host cities, stadium preparations, tournament format, dates, or other major news).\n\n"
    "Based on your search findings:\n"
    "1. Determine if there is new, interesting, or noteworthy information to share. If there is no new info, or if the news is repetitive/stale since your last update, set the status to 'SKIP'.\n"
    "2. If there is news, set the status to 'POST' and write a high-quality, engaging, and easy-to-understand Telegram post in 'post_content'.\n"
    "   - Use bullet points and emojis to make it visually appealing.\n"
    "   - Use relevant hashtags (e.g., #FIFA2026, #WorldCup, #Soccer, #Football).\n"
    "   - Style the text using ONLY these Telegram-supported HTML tags: <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strikethrough</s>, <code class=\"\">code</code>, and <a href=\"...\">links</a>. Do NOT use markdown (like **bold** or *italic*) inside 'post_content'. Ensure all HTML tags are correctly opened and closed.\n"
    "   - Keep the content length strictly under 950 characters (including hashtags and emojis) to ensure it fits in a Telegram photo caption.\n"
    "3. Generate a detailed, descriptive prompt for Imagen 3 in 'image_prompt'. It should describe a high-quality, compelling, and relevant image matching the post (e.g., 'Concept art of a vibrant soccer stadium in North America filled with fans wearing flags, dramatic lighting, professional sports photography' or 'A soccer ball with the flags of USA, Canada, and Mexico painted on it, resting on a pristine green grass field under a sunny sky, high detail'). Avoid generic quality words like 'photorealistic'."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {
            "type": "STRING",
            "enum": ["POST", "SKIP"],
            "description": "Whether to post new content or skip."
        },
        "post_content": {
            "type": "STRING",
            "description": "The HTML formatted post content. Max 950 characters."
        },
        "image_prompt": {
            "type": "STRING",
            "description": "A detailed image generation prompt for the news post."
        }
    },
    "required": ["status", "post_content", "image_prompt"]
}

def get_env_var(name):
    val = os.environ.get(name)
    if not val:
        print(f"Error: Environment variable '{name}' is not set.")
        sys.exit(1)
    return val

def clean_html(text):
    # Strip HTML tags in case Telegram rejects the message formatting
    return re.sub(r'<[^>]+>', '', text)

def fetch_fifa_news(api_key):
    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.7
        }
    }
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            print(f"Attempting to fetch news using model: {model}...")
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Model {model} failed with status code {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Model {model} request failed with error: {e}")
            
    # Fallback request without responseSchema (in case of schema constraints with tools in API)
    print("Attempting fallback request without responseSchema...")
    payload_fallback = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT + "\n\nYou MUST return the response as a valid JSON object matching the JSON schema format described above."}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7
        }
    }
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload_fallback, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Fallback model {model} failed: {e}")
            
    raise Exception("All Gemini API generation attempts failed.")

def parse_gemini_response(resp_json):
    try:
        candidates = resp_json.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned from Gemini.")
        
        text = candidates[0]["content"]["parts"][0]["text"]
        text_clean = text.strip()
        if text_clean.startswith("```json"):
            text_clean = text_clean[7:]
        if text_clean.endswith("```"):
            text_clean = text_clean[:-3]
        text_clean = text_clean.strip()
        
        return json.loads(text_clean)
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response structure: {json.dumps(resp_json, indent=2)[:500]}...")
        raise

def generate_image(api_key, prompt):
    models = ["imagen-3.0-generate-002", "imagen-3.0-generate-001"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        payload = {
            "instances": [
                {
                    "prompt": prompt
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "1:1",
                "outputMimeType": "image/jpeg"
            }
        }
        try:
            print(f"Attempting to generate image using model: {model}...")
            response = requests.post(url, json=payload, timeout=45)
            if response.status_code == 200:
                resp_json = response.json()
                predictions = resp_json.get("predictions", [])
                if predictions and "bytesBase64Encoded" in predictions[0]:
                    img_b64 = predictions[0]["bytesBase64Encoded"]
                    return base64.b64decode(img_b64)
                else:
                    print(f"Unexpected prediction response format: {resp_json}")
            else:
                print(f"Model {model} failed with status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Model {model} image generation failed: {e}")
            
    print("All image generation models failed or are not accessible with the provided key. Continuing without image.")
    return None

def send_to_telegram(bot_token, chat_id, text, image_bytes):
    if image_bytes:
        # Check if text fits inside the photo caption (limit is 1024 characters)
        if len(text) <= 1024:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("fifa2026.jpg", image_bytes, "image/jpeg")}
            data = {
                "chat_id": chat_id,
                "caption": text,
                "parse_mode": "HTML"
            }
            print("Sending image with caption to Telegram...")
            response = requests.post(url, files=files, data=data, timeout=30)
            
            # If the HTML parsing fails, fallback to sending stripped plain text
            if response.status_code == 400 and "can't parse entities" in response.text:
                print("HTML parsing failed on Telegram. Retrying with plain text caption...")
                plain_text = clean_html(text)
                if len(plain_text) > 1024:
                    plain_text = plain_text[:1020] + "..."
                data["caption"] = plain_text
                data.pop("parse_mode", None)
                response = requests.post(url, files=files, data=data, timeout=30)
                
            if response.status_code == 200:
                print("Successfully sent image with caption to Telegram.")
                return True
            else:
                print(f"Failed to send photo: {response.status_code} - {response.text}")
                print("Falling back to sending photo and text separately...")
        
        # If caption is too long (>1024) or joint sending failed, send separately
        # 1. Send the photo first with a generic placeholder
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        files = {"photo": ("fifa2026.jpg", image_bytes, "image/jpeg")}
        data = {
            "chat_id": chat_id,
            "caption": "⚽ FIFA World Cup 2026 Update! Details below 👇"
        }
        print("Sending photo to Telegram...")
        photo_response = requests.post(url, files=files, data=data, timeout=30)
        
        # 2. Send the full text as a reply or follow-up message
        url_msg = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data_msg = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if photo_response.status_code == 200:
            try:
                photo_data = photo_response.json()
                message_id = photo_data.get("result", {}).get("message_id")
                if message_id:
                    data_msg["reply_to_message_id"] = message_id
            except Exception as e:
                print(f"Could not parse photo message ID: {e}")
                
        print("Sending text message to Telegram...")
        response = requests.post(url_msg, json=data_msg, timeout=30)
        
        if response.status_code == 400 and "can't parse entities" in response.text:
            print("HTML parsing failed. Retrying text message as plain text...")
            data_msg["text"] = clean_html(text)
            data_msg.pop("parse_mode", None)
            response = requests.post(url_msg, json=data_msg, timeout=30)
            
        if response.status_code == 200:
            print("Successfully sent photo and text separately.")
            return True
        else:
            print(f"Failed to send separate text: {response.status_code} - {response.text}")
            
    # Text-only fallback (if image generation failed or was completely rejected)
    print("Sending text-only message to Telegram...")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=data, timeout=30)
    
    if response.status_code == 400 and "can't parse entities" in response.text:
        print("HTML parsing failed. Retrying plain text message...")
        data["text"] = clean_html(text)
        data.pop("parse_mode", None)
        response = requests.post(url, json=data, timeout=30)
        
    if response.status_code == 200:
        print("Successfully sent text-only message.")
        return True
    else:
        print(f"Failed to send text-only message: {response.status_code} - {response.text}")
        return False

def main():
    # Read and validate secrets
    gemini_key = get_env_var("GEMINI_API_KEY")
    tg_token = get_env_var("TELEGRAM_BOT_TOKEN")
    tg_chat_id = get_env_var("TELEGRAM_CHAT_ID")
    
    print("Fetching FIFA 2026 news from Gemini API...")
    try:
        resp = fetch_fifa_news(gemini_key)
        parsed_data = parse_gemini_response(resp)
    except Exception as e:
        print(f"Error during Gemini news retrieval: {e}")
        sys.exit(1)
        
    status = parsed_data.get("status", "SKIP").upper()
    print(f"Decision from AI: {status}")
    
    if status == "SKIP":
        print("Silent skip requested by AI. Exiting...")
        sys.exit(0)
        
    post_content = parsed_data.get("post_content", "").strip()
    image_prompt = parsed_data.get("image_prompt", "").strip()
    
    if not post_content:
        print("Warning: post_content is empty. Exiting...")
        sys.exit(0)
        
    image_bytes = None
    if image_prompt:
        print(f"Generating image with prompt: {image_prompt}")
        image_bytes = generate_image(gemini_key, image_prompt)
    else:
        print("No image prompt was generated by the AI.")
        
    success = send_to_telegram(tg_token, tg_chat_id, post_content, image_bytes)
    if not success:
        print("Failed to post message to Telegram.")
        sys.exit(1)
        
    print("Automation run completed successfully!")

if __name__ == "__main__":
    main()
