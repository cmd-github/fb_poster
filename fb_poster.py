import requests
import random
import os
import json
import argparse
import logging

# Set up logging to track success or errors
logging.basicConfig(filename='facebook_poster.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Argument parser for client-specific configurations
parser = argparse.ArgumentParser(description="Post to Facebook for clients")
parser.add_argument('--client', required=True, help="Client name (e.g., 'me', 'ryan', 'paul')")
parser.add_argument('--msg-file', required=True, help="Message file (e.g., 'ai_tips.txt')")
parser.add_argument('--msg-mode', choices=['random', 'sequential'], default='random', 
                    help="Message selection mode: 'random' or 'sequential'")
parser.add_argument('--photo-mode', choices=['random', 'sequential'], default='random', 
                    help="Photo selection mode: 'random' or 'sequential'")
parser.add_argument('--photo-dir', default='images', help="Base directory for photos")
args = parser.parse_args()

# Load tokens: Try environment variable first (GitHub Actions), then fallback to local tokens.json
tokens_json = os.getenv("TOKENS")
if tokens_json:
    TOKENS = json.loads(tokens_json)
else:
    try:
        with open('tokens.json', 'r') as f:
            TOKENS = json.load(f)
    except FileNotFoundError:
        logging.error("No TOKENS env var or tokens.json found")
        raise FileNotFoundError("Please set TOKENS env var or provide tokens.json with client credentials")

# Get client-specific tokens
client = args.client
if client not in TOKENS:
    logging.error(f"No credentials found for client: {client}")
    raise ValueError(f"Client '{client}' not found in tokens")
fb_page_access_token = TOKENS[client]["FB_PAGE_TOKEN"]
fb_page_id = TOKENS[client]["FB_PAGE_ID"]

# Check if tokens are valid
if not fb_page_access_token or not fb_page_id:
    logging.error(f"Missing FB_PAGE_TOKEN or FB_PAGE_ID for client: {client}")
    raise ValueError(f"FB_PAGE_TOKEN or FB_PAGE_ID missing for client: {client}")

# Progress tracking for sequential mode
PROGRESS_FILE = f"progress_{client}.json"
def load_progress():
    """Load the current index for sequential posting."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"msg_index": 0, "photo_index": 0}

def save_progress(msg_index, photo_index):
    """Save the updated index for sequential posting."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"msg_index": msg_index, "photo_index": photo_index}, f)

# Function to get a message
def get_message(filename, mode):
    """Get a message from the file based on mode (random or sequential)."""
    try:
        with open(filename, 'r') as file:
            messages = [line.strip() for line in file if line.strip()]  # Remove empty lines
        if not messages:
            logging.warning(f"{filename} is empty; using default message")
            return "Default message"
        
        if mode == 'random':
            return random.choice(messages)
        else:  # sequential
            progress = load_progress()
            index = progress["msg_index"]
            msg = messages[index % len(messages)]  # Loop if end reached
            progress["msg_index"] = index + 1
            save_progress(progress["msg_index"], progress["photo_index"])
            return msg
    except FileNotFoundError:
        logging.error(f"Message file not found: {filename}")
        raise FileNotFoundError(f"Please create {filename} with some messages")

# Function to get an image
def get_image(base_dir, mode):
    """Get an image from the client's folder based on mode (random or sequential)."""
    image_dir = os.path.join(base_dir, client)  # e.g., images/me, images/ryan
    try:
        images = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if not images:
            raise ValueError(f"No images found in {image_dir}")
        
        if mode == 'random':
            return os.path.join(image_dir, random.choice(images))
        else:  # sequential
            progress = load_progress()
            sorted_images = sorted(images)  # Alphabetical order
            index = progress["photo_index"]
            image = sorted_images[index % len(sorted_images)]  # Loop if end reached
            progress["photo_index"] = index + 1
            save_progress(progress["msg_index"], progress["photo_index"])
            return os.path.join(image_dir, image)
    except FileNotFoundError:
        logging.error(f"Image folder not found: {image_dir}")
        raise FileNotFoundError(f"Please create {image_dir} with some images")

# Function to post to Facebook
def post_to_facebook(image_path, caption):
    """Post the image and caption to the client's Facebook Page."""
    fb_url = f"https://graph.facebook.com/{fb_page_id}/photos"
    logging.info(f"Uploading image from: {image_path} for client: {client}")
    try:
        with open(image_path, 'rb') as image_file:
            file_ext = os.path.splitext(image_path)[1].lower()
            fb_payload = {
                "caption": caption,
                "access_token": fb_page_access_token
            }
            fb_files = {
                "source": (os.path.basename(image_path), image_file, 
                          'image/png' if file_ext == '.png' else 'image/jpeg')
            }
            response = requests.post(fb_url, data=fb_payload, files=fb_files)
            response.raise_for_status()
            logging.info(f"Successfully posted to Facebook for {client}: {caption}")
            print(f"Posted: {caption} with {image_path}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to post to Facebook for {client}: {e} - Response: {response.text}")
        print(f"Error posting: {e} - Response: {response.text}")
    except FileNotFoundError:
        logging.error(f"Image file not found: {image_path}")
        print(f"Image file not found: {image_path}")

# Main execution
if __name__ == "__main__":
    try:
        # Get content based on client config
        caption = get_message(args.msg_file, args.msg_mode)
        image_path = get_image(args.photo_dir, args.photo_mode)
        
        # Post to Facebook
        print(f"Attempting to post for {client}: {caption} with {image_path}")
        post_to_facebook(image_path, caption)
        
    except Exception as e:
        logging.error(f"Script failed for {client}: {e}")
        print(f"Script failed: {e}")