import os
import json
import urllib.request
from datetime import datetime

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not all([HF_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    missing = []
    if not HF_TOKEN: missing.append('HF_TOKEN')
    if not TELEGRAM_BOT_TOKEN: missing.append('TELEGRAM_BOT_TOKEN')
    if not TELEGRAM_CHAT_ID: missing.append('TELEGRAM_CHAT_ID')
    print(f'ERROR: Missing environment variables: {", ".join(missing)}')
    exit(1)

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
        with urllib.request.urlopen(req) as resp:
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
    data = '\r\n'.join(body)
    req = urllib.request.Request(url, data=data.encode('utf-8'), headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    })
    try:
        with urllib.request.urlopen(req) as resp:
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
    
    text_data = json.dumps(text_payload).encode('utf-8')
    text_req = urllib.request.Request(text_api_url, data=text_data, headers=text_headers)
    try:
        with urllib.request.urlopen(text_req) as resp:
            text_result = json.load(resp)
            generated_text = text_result[0]['generated_text'] if isinstance(text_result, list) and len(text_result) > 0 else ""
    except Exception as e:
        print('Error calling Hugging Face text API:', e)
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
    image_data = json.dumps(image_payload).encode('utf-8')
    image_req = urllib.request.Request(image_api_url, data=image_data, headers=image_headers, method='POST')
    try:
        with urllib.request.urlopen(image_req) as resp:
            if resp.getcode() == 200:
                image_bytes = resp.read()
                print(f'Generated image size: {len(image_bytes)} bytes')
                # Send photo with caption
                send_telegram_photo(image_bytes, caption=message)
            else:
                print(f'Image generation failed with status {resp.getcode()}')
                # Fallback: send only message
                send_telegram_message(message)
    except Exception as e:
        print('Error calling Hugging Face image API:', e)
        # Fallback: send only message
        send_telegram_message(message)
    
    print('Notification processed.')

if __name__ == '__main__':
    main()