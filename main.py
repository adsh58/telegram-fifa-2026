import os
import sys
import json
import re
import random
import time
import requests

# Persistent history file to avoid repeating news topics
HISTORY_FILE = "post_history.txt"

# Curated pool of professional soccer and stadium images
IMAGE_POOL = {
    "stadium_sunset": "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?auto=format&fit=crop&w=1200&q=80",
    "stadium_pitch": "https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=1200&q=80",
    "soccer_ball_grass": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80",
    "goal_moment": "https://images.unsplash.com/photo-1551958219-acbc608c6377?auto=format&fit=crop&w=1200&q=80",
    "soccer_field_aerial": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1200&q=80",
    "fans_celebrating": "https://images.unsplash.com/photo-1510563800743-aed2364902b8?auto=format&fit=crop&w=1200&q=80",
    "action_shot": "https://images.unsplash.com/photo-1504155611831-7214b4686d26?auto=format&fit=crop&w=1200&q=80",
    "field_close_up": "https://images.unsplash.com/photo-1431324155629-1a6edd1796b5?auto=format&fit=crop&w=1200&q=80",
    "sunset_pitch": "https://images.unsplash.com/photo-1518063319789-7217e6706b04?auto=format&fit=crop&w=1200&q=80",
    "boots_and_ball": "https://images.unsplash.com/photo-1568194157720-8eae79a37bac?auto=format&fit=crop&w=1200&q=80",
    "training_ground": "https://images.unsplash.com/photo-1516222338250-863216ce01fa?auto=format&fit=crop&w=1200&q=80"
}

# Rotating topics to search for different areas of FIFA 2026
FOCUS_TOPICS = [
    "latest qualifiers status, continental matches highlights and team standings worldwide for World Cup 2026",
    "host cities spotlight (like Toronto, Vancouver, Mexico City, Guadalajara, Monterrey, Miami, Seattle, New York, etc.) and stadium construction/renovation progress",
    "tournament format updates (48 teams, 12 groups of 4, number of matches, knockout stage details, match schedule)",
    "rising young soccer stars and top ballers expected to shine in 2026, their current club/national form and stats",
    "tactical shifts, soccer formations (like 3-4-3 or 4-3-3), and coaching strategies being prepared for the World Cup",
    "ticketing details, volunteer registration, fan zones plans, and local host committee announcements",
    "historical milestones and trivia connecting host countries (USA, Canada, Mexico) to past World Cup tournaments",
    "CONCACAF, UEFA, CONMEBOL, AFC, CAF qualifiers highlights, group draws, and key upcoming qualification matches"
]

PROMPT_TEMPLATE = (
    "You are a professional sports journalist and social media manager specializing in international soccer/football.\n"
    "Search for the latest news, updates, announcements, or key details about the upcoming FIFA World Cup 2026, specifically focusing on this area: {selected_topic}.\n\n"
    "To prevent repeating information that has already been posted, here are the topics/headlines of recently published posts:\n"
    "{history_text}\n\n"
    "DO NOT repeat or write about the exact same stories or headlines listed in the history. Focus on new details, different teams/cities, or an entirely fresh perspective based on the current search.\n\n"
    "Based on your search findings:\n"
    "1. Determine if there is new, interesting, or noteworthy information to share. If there is no new info, or if the news is repetitive/stale compared to the history, set the status to 'SKIP'.\n"
    "2. If there is news, set the status to 'POST' and write a high-quality, engaging, and easy-to-understand Telegram post in 'post_content'.\n"
    "   - Use bold uppercase headers and emojis to make it look premium (e.g. <b>🚨 WORLD CUP 2026 BUZZ 🚨</b> or <b>WC2026 INSIDER REPORT! ⚡</b>).\n"
    "   - Structure it with bullet points using '*' and bold introductory words (e.g., '* <b>A young gun phenom</b> is on...').\n"
    "   - Make it read dynamically and cleanly, with a conversational, high-quality tone.\n"
    "   - Ask an engaging question at the end to prompt response/discussion.\n"
    "   - Use space-separated hashtags at the very end of the post (e.g., #WC2026 #FootballHype #RoadTo2026).\n"
    "   - Style the text using ONLY these Telegram-supported HTML tags: <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strikethrough</s>, <code>code</code>, and <a href=\"...\">links</a>. Do NOT use markdown (like **bold** or *italic*) inside 'post_content'. Ensure all HTML tags are correctly opened and closed.\n"
    "   - Keep the content length strictly under 950 characters (including hashtags and emojis) to ensure it fits in a Telegram photo caption.\n"
    "3. Select the best matching image from the following options for the post content and return its key in 'image_key':\n"
    "   - 'stadium_sunset': A modern stadium grandstand at sunset.\n"
    "   - 'stadium_pitch': An illuminated stadium pitch with spotlights.\n"
    "   - 'soccer_ball_grass': A professional soccer ball resting on green grass.\n"
    "   - 'goal_moment': A soccer ball hitting the back of the net.\n"
    "   - 'soccer_field_aerial': Aerial view of a lush green soccer field.\n"
    "   - 'fans_celebrating': Excited fans celebrating in a stadium.\n"
    "   - 'action_shot': A player kick action shot vibe.\n"
    "   - 'field_close_up': A close-up of grass and a corner flag.\n"
    "   - 'sunset_pitch': A local soccer field under a sunset sky.\n"
    "   - 'boots_and_ball': A soccer ball and boots on artificial turf.\n"
    "   - 'training_ground': Training session cones and soccer balls.\n"
    "4. Return a short, 1-sentence summary of the main headline or topic of this post in 'headline_summary' (max 60 characters) so we can add it to the history list."
)

def get_env_var(name):
    val = os.environ.get(name)
    if not val:
        print(f"Error: Environment variable '{name}' is not set.")
        sys.exit(1)
    return val

def clean_html(text):
    # Strip HTML tags in case Telegram rejects the message formatting
    return re.sub(r'<[^>]+>', '', text)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading history: {e}")
    return []

def save_history(history_list, new_entry):
    history_list.append(new_entry)
    # Keep only the last 10 entries
    history_list = history_list[-10:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for entry in history_list:
                f.write(entry + "\n")
        print("Updated history file successfully.")
    except Exception as e:
        print(f"Error saving history: {e}")

def make_request_with_retries(url, payload, max_retries=3):
    """
    Makes a POST request and retries on 429 (Rate Limit) or 503 (Unavailable) errors
    with exponential backoff and respect for Google's retryDelay.
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response
            
            # Check for temporary service issues or rate limits
            if response.status_code in (429, 503):
                wait_time = 10  # default wait time
                try:
                    # Attempt to parse Google's detailed rate limit retry delay
                    resp_json = response.json()
                    error_details = resp_json.get("error", {}).get("details", [])
                    for detail in error_details:
                        if "retryDelay" in detail:
                            delay_str = detail["retryDelay"].replace("s", "")
                            wait_time = int(float(delay_str)) + 1
                            break
                except Exception:
                    pass
                
                # Check standard Retry-After header
                if "Retry-After" in response.headers:
                    try:
                        wait_time = int(response.headers["Retry-After"])
                    except Exception:
                        pass
                
                # Apply backoff scaling on subsequent attempts
                wait_time = wait_time * (attempt + 1)
                print(f"Received status {response.status_code} on attempt {attempt+1}/{max_retries}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # Do not retry on permanent errors (400, 404, etc.)
                return response
        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise
    return None

def fetch_fifa_news(api_key, selected_topic, history_list):
    # Robust selection of models including stable fallbacks
    models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash-latest"
    ]
    
    history_text = "\n".join([f"- {h}" for h in history_list]) if history_list else "No previous posts."
    prompt = PROMPT_TEMPLATE.format(selected_topic=selected_topic, history_text=history_text)
    
    # Instruct the model to return its response in JSON format.
    prompt_with_instructions = (
        prompt + 
        "\n\nIMPORTANT: You must return your response EXACTLY as a valid JSON object. "
        "Do not include any other conversational text or explanations. Return it in this format:\n"
        "{\n"
        "  \"status\": \"POST\" or \"SKIP\",\n"
        "  \"post_content\": \"HTML formatted telegram post\",\n"
        "  \"image_key\": \"Key of the selected image from the list\",\n"
        "  \"headline_summary\": \"Short 1-sentence summary of this post\"\n"
        "}"
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_with_instructions}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "temperature": 0.7
        }
    }
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            print(f"Attempting to fetch news using model: {model}...")
            response = make_request_with_retries(url, payload)
            if response and response.status_code == 200:
                return response.json()
            elif response:
                print(f"Model {model} failed with status code {response.status_code}: {response.text}")
            else:
                print(f"Model {model} failed (no response received).")
        except Exception as e:
            print(f"Model {model} request failed with error: {e}")
            
    raise Exception("All Gemini API generation attempts failed after retries.")

def parse_gemini_response(resp_json):
    text = ""
    try:
        candidates = resp_json.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned from Gemini.")
        
        text = candidates[0]["content"]["parts"][0]["text"]
        text_clean = text.strip()
        
        # Extract JSON from markdown blocks if present
        if "```json" in text_clean:
            match = re.search(r"```json\s*(.*?)\s*```", text_clean, re.DOTALL)
            if match:
                text_clean = match.group(1)
        elif "```" in text_clean:
            match = re.search(r"```\s*(.*?)\s*```", text_clean, re.DOTALL)
            if match:
                text_clean = match.group(1)
                
        text_clean = text_clean.strip()
        return json.loads(text_clean)
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response text: {text}")
        raise

def send_to_telegram(bot_token, chat_id, text, image_url):
    if image_url:
        # Check if text fits inside the photo caption (limit is 1024 characters)
        if len(text) <= 1024:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            data = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": text,
                "parse_mode": "HTML"
            }
            print(f"Sending image URL {image_url} with caption to Telegram...")
            response = requests.post(url, json=data, timeout=30)
            
            # If the HTML parsing fails, fallback to sending stripped plain text
            if response.status_code == 400 and "can't parse entities" in response.text:
                print("HTML parsing failed on Telegram. Retrying with plain text caption...")
                plain_text = clean_html(text)
                if len(plain_text) > 1024:
                    plain_text = plain_text[:1020] + "..."
                data["caption"] = plain_text
                data.pop("parse_mode", None)
                response = requests.post(url, json=data, timeout=30)
                
            if response.status_code == 200:
                print("Successfully sent image with caption to Telegram.")
                return True
            else:
                print(f"Failed to send photo: {response.status_code} - {response.text}")
                print("Falling back to sending photo and text separately...")
        
        # If caption is too long (>1024) or joint sending failed, send separately
        # 1. Send the photo first
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        data = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": "⚽ FIFA World Cup 2026 Update! Details below 👇"
        }
        print("Sending photo to Telegram...")
        photo_response = requests.post(url, json=data, timeout=30)
        
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
            
    # Text-only fallback (if image_url is None or photo sending completely failed)
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
    
    # Load past history
    history_list = load_history()
    
    # Pick a random topic to force query diversification
    selected_topic = random.choice(FOCUS_TOPICS)
    print(f"Chosen topic focus for this run: '{selected_topic}'")
    
    print("Fetching FIFA 2026 news from Gemini API...")
    try:
        resp = fetch_fifa_news(gemini_key, selected_topic, history_list)
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
    image_key = parsed_data.get("image_key", "soccer_ball_grass").strip()
    headline_summary = parsed_data.get("headline_summary", "").strip()
    
    if not post_content:
        print("Warning: post_content is empty. Exiting...")
        sys.exit(0)
        
    # Get the image URL from our curated pool based on the AI's selection
    image_url = IMAGE_POOL.get(image_key, IMAGE_POOL["soccer_ball_grass"])
    print(f"Selected image URL: {image_url} (Key: {image_key})")
        
    success = send_to_telegram(tg_token, tg_chat_id, post_content, image_url)
    if not success:
        print("Failed to post message to Telegram.")
        sys.exit(1)
        
    # Save the headline summary to history to prevent future repetition
    if headline_summary:
        save_history(history_list, headline_summary)
        
    print("Automation run completed successfully!")

if __name__ == "__main__":
    main()
