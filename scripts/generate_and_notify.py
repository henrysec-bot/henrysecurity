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

# For command bot mode
BOT_MODE = os.getenv('BOT_MODE', 'scheduled').strip()  # 'scheduled' or 'command'
COMMAND_CHAT_ID = os.getenv('COMMAND_CHAT_ID', TELEGRAM_CHAT_ID).strip()  # Chat to listen for commands
ODIN_CHAT_ID = os.getenv('ODIN_CHAT_ID', '-576735827').strip()  # O.D.I.N. group ID

if not all([HF_TOKEN, TELEGRAM_BOT_TOKEN]):
    missing = []
    if not HF_TOKEN: missing.append('HF_TOKEN')
    if not TELEGRAM_BOT_TOKEN: missing.append('TELEGRAM_BOT_TOKEN')
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
def send_telegram_message(chat_id, text):
    """Send message to a specific chat ID."""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': text
    }
    data_encoded = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_encoded, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.load(resp)
            if result.get('ok'):
                print(f'Message sent successfully to chat {chat_id}')
                return True
            else:
                print(f'Telegram API error: {result}')
                return False
    except Exception as e:
        print(f'Failed to send Telegram message to chat {chat_id}: {e}')
        return False

def send_telegram_photo(chat_id, photo_bytes, caption=''):
    """Send photo to a specific chat ID."""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = []
    # chat_id
    body.append(f'--{boundary}')
    body.append('Content-Disposition: form-data; name="chat_id"')
    body.append('')
    body.append(str(chat_id))
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
    data = '\r\n'.join(body)
    req = urllib.request.Request(url, data=data.encode('utf-8'), headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.load(resp)
            if result.get('ok'):
                print(f'Photo sent successfully to chat {chat_id}')
                return True
            else:
                print(f'Telegram API error: {result}')
                return False
    except Exception as e:
        print(f'Failed to send Telegram photo to chat {chat_id}: {e}')
        return False

def get_otx_pulse():
    # For now, we'll return a static topic; in the future we could fetch from OTX API
    return {
        'title': 'Vulnerabilidade crítica em software de ponto de venda',
        'description': 'Descoberta de uma falha que permite acesso remoto a sistemas de PDV.',
        'link': 'https://otx.alienvault.com/pulse/placeholder'
    }

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

def format_telegram_message(content):
    """Format content for Telegram message."""
    return f"""*Legenda para Instagram:*
{content['caption']}

*Hashtags sugeridas:*
{' '.join(content['hashtags'])}

*Prompt para imagem (SDXL):*
{content['image_prompt']}

*Fonte:* {content['link']}
"""

def handle_scheduled_run():
    """Original scheduled behavior - generate and send to marketing chat."""
    print('Starting HSEC Marketing Agent (scheduled mode)...')
    print(f'Time: {datetime.now()}')
    
    topic = get_otx_pulse()
    print(f'Topic: {topic["title"]}')
    
    content = generate_content(topic)
    print('Generated content:')
    print(f'  Caption: {content["caption"]}')
    print(f'  Hashtags: {" ".join(content["hashtags"])}')
    print(f'  Image prompt: {content["image_prompt"]}')
    
    # Build Telegram message (text part)
    message = format_telegram_message(content)
    
    # Generate image using Hugging Face
    image_api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    image_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    image_payload = {"inputs": content["image_prompt"]}
    
    image_bytes = hf_post(image_api_url, image_payload, image_headers, timeout=60, max_retries=2)
    if image_bytes is not None:
        print(f'Generated image size: {len(image_bytes)} bytes')
        # Send photo with caption to marketing chat
        send_telegram_message(TELEGRAM_CHAT_ID, message)
        # send_telegram_photo(TELEGRAM_CHAT_ID, image_bytes, caption=message)  # Disabled for simplicity
    else:
        print('Image generation failed after retries; sending only message')
        send_telegram_message(TELEGRAM_CHAT_ID, message)
    
    print('Notification processed.')

def handle_command_mode():
    """Bot that listens for and responds to commands."""
    print('Starting HSEC Marketing Agent (command mode)...')
    print(f'Listening for commands in chat: {COMMAND_CHAT_ID}')
    print(f'ODIN chat ID: {ODIN_CHAT_ID}')
    
    offset = 0
    while True:
        try:
            # Get updates
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=30'
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.load(resp)
                
                if result.get('ok'):
                    updates = result.get('result', [])
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            message = update['message']
                            chat_id = str(message['chat']['id'])
                            text = message.get('text', '')
                            from_user = message.get('from', {})
                            user_id = str(from_user.get('id', ''))
                            username = from_user.get('username', '')
                            
                            print(f'Received message from {user_id} (@{username}) in chat {chat_id}: {text}')
                            
                            # Check if it's a command
                            if text.startswith('/'):
                                handle_command(chat_id, text, user_id, username)
                else:
                    print(f'Error getting updates: {result}')
                    time.sleep(5)
                    
        except Exception as e:
            print(f'Error in command loop: {e}')
            time.sleep(5)

def handle_command(chat_id, command_text, user_id, username):
    """Handle a command received from a user."""
    parts = command_text.split()
    cmd = parts[0].lower()
    
    print(f'Handling command: {cmd} from user {user_id} in chat {chat_id}')
    
    if cmd == '/ajuda' or cmd == '/help':
        help_text = """*HSEC Marketing Agent - Comandos Disponíveis:*

/gerar [tópico] - Gera conteúdo de marketing imediatamente
/status - Verifica se o bot está ativo
/ajuda - Mostra esta ajuda

*Exemplos:*
/gerar vulnerabilidade em sistemas de pagamento
/gerar novo malware bancário

O bot também responde a menções de 'O.D.I.N.' enviando relatórios para o grupo do O.D.I.N."""
        send_telegram_message(chat_id, help_text)
        
    elif cmd == '/status':
        status_text = f"""*HSEC Marketing Agent - Status:*
✅ Bot ativo e ouvindo comandos
🕒 Hora local: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
🎯 Chat de comandos: {chat_id}
🔗 Token HF: {'Configurado' if HF_TOKEN else 'Não configurado'}
📱 Token Telegram: {'Configurado' if TELEGRAM_BOT_TOKEN else 'Não configurado'}"""
        send_telegram_message(chat_id, status_text)
        
    elif cmd == '/gerar':
        # Extract topic if provided
        if len(parts) > 1:
            topic_title = ' '.join(parts[1:])
            topic = {
                'title': topic_title,
                'description': f'Tópico solicitado via comando: {topic_title}',
                'link': 'https://henrysecurity.com.br'
            }
        else:
            # Use default OTX pulse
            topic = get_otx_pulse()
        
        print(f'Generating content for topic: {topic["title"]}')
        content = generate_content(topic)
        message = format_telegram_message(content)
        
        # Determine where to send the result
        # If command mentions O.D.I.N., send to O.D.I.N. group
        # Otherwise, send to the chat where command was received
        if 'odin' in command_text.lower() or 'o.d.i.n.' in command_text.lower():
            target_chat = ODIN_CHAT_ID
            print(f'Sending result to O.D.I.N. group: {ODIN_CHAT_ID}')
        else:
            target_chat = chat_id
            print(f'Sending result to originating chat: {chat_id}')
        
        # Generate image and send
        image_api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        image_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        image_payload = {"inputs": content["image_prompt"]}
        
        image_bytes = hf_post(image_api_url, image_payload, image_headers, timeout=60, max_retries=2)
        if image_bytes is not None:
            print(f'Generated image size: {len(image_bytes)} bytes')
            # Send photo with caption
            send_telegram_photo(target_chat, image_bytes, caption=message)
        else:
            print('Image generation failed after retries; sending only message')
            send_telegram_message(target_chat, message)
            
    else:
        unknown_text = f"""Comando desconhecido: {cmd}
Use /ajuda para ver os comandos disponíveis."""
        send_telegram_message(chat_id, unknown_text)

def main():
    """Main entry point - determines mode based on environment."""
    print(f'HSEC Marketing Agent starting in {BOT_MODE} mode...')
    
    if BOT_MODE == 'command':
        handle_command_mode()
    else:
        # Default to scheduled mode for backward compatibility
        handle_scheduled_run()

if __name__ == '__main__':
    main()