import os
import json
import urllib.request
import urllib.error
import socket
import time
from datetime import datetime

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN', '').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()

if not all([HF_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    missing = []
    if not HF_TOKEN: missing.append('HF_TOKEN')
    if not TELEGRAM_BOT_TOKEN: missing.append('TELEGRAM_BOT_TOKEN')
    if not TELEGRAM_CHAT_ID: missing.append('TELEGRAM_CHAT_ID')
    print(f'ERROR: Missing environment variables: {", ".join(missing)}')
    exit(1)

def resolve_host(hostname, max_retries=3, delay=1):
    """Resolve hostname with retries."""
    for i in range(max_retries):
        try:
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror as e:
            if i < max_retries - 1:
                wait_time = delay * (2 ** i)  # exponential backoff
                print(f'DNS resolution failed for {hostname} (attempt {i+1}): {e}. Retrying in {wait_time}s...')
                time.sleep(wait_time)
            else:
                print(f'DNS resolution failed for {hostname} after {max_retries} attempts: {e}')
                return False
    return False

def hf_post(api_url, payload, headers, timeout=30, max_retries=3):
    """POST to Hugging Face Inference API with retries and timeout."""
    # Extract hostname for DNS pre-check
    from urllib.parse import urlparse
    parsed = urlparse(api_url)
    hostname = parsed.hostname
    if hostname and not resolve_host(hostname, max_retries=2, delay=1):
        print('Skipping HF API call due to DNS resolution failure')
        return None
        
    data = json.dumps(payload).encode('utf-8')
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(api_url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.getcode() == 200:
                    return resp.read()
                else:
                    print(f'HF API returned status {resp.getcode()} (attempt {attempt+1})')
                    if attempt == max_retries - 1:  # last attempt
                        # Try to read error body if available
                        try:
                            error_body = resp.read().decode('utf-8')
                            print(f'HF API error body: {error_body[:200]}')
                        except:
                            pass
        except urllib.error.URLError as e:
            print(f'HF API request failed (attempt {attempt+1}): {str(e)}')
            if hasattr(e, 'reason') and isinstance(e.reason, OSError):
                if e.reason.errno in (-5, 11001):  # DNS resolution errors
                    print('DNS resolution error - checking network...')
        except Exception as e:
            print(f'Unexpected error calling HF API (attempt {attempt+1}): {str(e)}')
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # exponential backoff: 1, 2, 4 seconds
            print(f'Retrying in {wait_time} seconds...')
            time.sleep(wait_time)
    return None

# Function to send message via Telegram
def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown'
    }
    data_encoded = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_encoded, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.load(resp)
            if result.get('ok'):
                print('Message sent successfully')
            else:
                print('Telegram API error:', result)
    except Exception as e:
        print('Failed to send Telegram message:', e)

# Function to send photo via Telegram (multipart/form-data)
def send_telegram_photo(photo_bytes, caption=''):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = []
    # chat_id
    body.append(f'--{boundary}')
    body.append('Content-Disposition: form-data; name="chat_id"')
    body.append('')
    body.append(str(TELEGRAM_CHAT_ID))
    # caption
    body.append(f'--{boundary}')
    body.append('Content-Disposition: form-data; name="caption"')
    body.append('')
    body.append(caption)
    # photo
    body.append(f'--{boundary}')
    body.append('Content-Disposition: form-data; name="photo"; filename="image.png"')
    body.append('Content-Type: image/png')
    body.append('')
    body.append(photo_bytes.decode('latin-1'))
    body.append(f'--{boundary}--')
    body.append('')
    data = '\\r\\n'.join(body)
    req = urllib.request.Request(url, data=data.encode('utf-8'), headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.load(resp)
            if result.get('ok'):
                print('Photo sent successfully')
            else:
                print('Telegram API error:', result)
    except Exception as e:
        print('Failed to send Telegram photo:', e)

# Function to get a topic from AlienVault OTX (example)
def get_otx_pulse():
    # For now, we'll return a static topic; in the future we could fetch from OTX API
    return {
        'title': 'Vulnerabilidade crítica em software de ponto de venda',
        'description': 'Descoberta de uma falha que permite acesso remoto a sistemas de PDV.',
        'link': 'https://otx.alienvault.com/pulse/placeholder'
    }

# Function to generate content using Hugging Face
def generate_content(topic):
    # Text generation
    text_api_url = "https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1"
    text_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    prompt = f"""Você é um agente de marketing da Henry Security, uma empresa de cibersegurança.
    Crie uma legenda educativa e descontraída para o Instagram sobre o seguinte tema:
    {topic['title']}
    {topic['description']}
    
    A legenda deve ter até 200 caracteres, incluir uma chamada para ação suave e ser relevante para profissionais de TI e PMEs.
    Também sugira 5-7 hashtags em português e inglês.
    Por fim, forneça um prompt em inglês para geração de imagem com Stable Diffusion XL que illustre o tema.
    """
    
    text_payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.7,
            "top_p": 0.9,
            "return_full_text": False
        }
    }
    
    image_bytes = hf_post(text_api_url, text_payload, text_headers, timeout=30, max_retries=3)
    generated_text = ''
    if image_bytes is not None:
        try:
            text_result = json.loads(image_bytes.decode('utf-8'))
            # The API returns a list of dicts with generated_text
            if isinstance(text_result, list) and len(text_result) > 0:
                generated_text = text_result[0].get('generated_text', '')
            else:
                generated_text = str(text_result)
        except Exception as e:
            print('Error parsing HF text response:', e)
            generated_text = f'Fique atento! {topic["title"]} - {topic["description"][:100]}...'
    else:
        generated_text = f'Fique atento! {topic["title"]} - {topic["description"][:100]}...'
    
    # For hashtags and image prompt, we'll use simple extraction or defaults
    hashtags = ['#HenrySecurity', '#Cibersegurança', '#DicaDeSegurança', '#Vazamento', '#Tecnologia']
    image_prompt = 'A futuristic digital shield protecting a computer network, neon blue and purple, cyberpunk style, detailed, 8k'
    
    return {
        'caption': generated_text[:200] if len(generated_text) > 200 else generated_text,
        'hashtags': hashtags,
        'image_prompt': image_prompt,
        'link': topic.get('link', '')
    }

def main():
    print('Starting HSEC Marketing Agent...')
    print(f'Time: {datetime.now()}')
    
    topic = get_otx_pulse()
    print(f'Topic: {topic["title"]}')
    
    content = generate_content(topic)
    print('Generated content:')
    print(f'  Caption: {content["caption"]}')
    print(f'  Hashtags: {" ".join(content["hashtags"])}')
    print(f'  Image prompt: {content["image_prompt"]}')
    
    # Build Telegram message (text part)
    message = f"""*Legenda para Instagram:*
{content['caption']}

*Hashtags sugeridas:*
{' '.join(content['hashtags'])}

*Prompt para imagem (SDXL):*
{content['image_prompt']}

*Fonte:* {content['link']}
"""
    
    # Generate image using Hugging Face
    image_api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    image_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    image_payload = {"inputs": content["image_prompt"]}
    
    image_bytes = hf_post(image_api_url, image_payload, image_headers, timeout=60, max_retries=2)
    if image_bytes is not None:
        print(f'Generated image size: {len(image_bytes)} bytes')
        # Send photo with caption
        send_telegram_photo(image_bytes, caption=message)
    else:
        print('Image generation failed after retries; sending only message')
        send_telegram_message(message)
    
    print('Notification processed.')

if __name__ == '__main__':
    main()