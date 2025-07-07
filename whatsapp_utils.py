import requests
import json
import config # Importa as configurações

def enviar_mensagem_whatsapp(numero_destino, mensagem_texto):
    print(f"DEBUG WA_UTILS: Entrou em enviar_mensagem_whatsapp para {numero_destino}")
    if not config.WHATSAPP_ACCESS_TOKEN or not config.WHATSAPP_PHONE_NUMBER_ID:
        print(f"ERRO WA_UTILS: WHATSAPP_TOKEN ou WHATSAPP_PHONE_NUMBER_ID não configurados.")
        print(f"DEBUG WA_UTILS: Token='{config.WHATSAPP_ACCESS_TOKEN}', PhoneID='{config.WHATSAPP_PHONE_NUMBER_ID}'")
        return False

    url = f"https://graph.facebook.com/{config.WHATSAPP_GRAPH_API_VERSION}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": numero_destino, "type": "text", "text": {"body": mensagem_texto}}
    
    print(f"DEBUG WA_UTILS: Enviando para URL: {url}, Payload: {json.dumps(payload)}")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"DEBUG WA_UTILS: Status Code da Meta: {response.status_code}")
        response.raise_for_status()
        response_data = response.json()
        print(f"Resposta API WhatsApp (WA_UTILS): {json.dumps(response_data, indent=2)}")
        if response_data.get("messages") and response_data["messages"][0].get("id"):
            print(f"Mensagem enviada OK para {numero_destino}. ID: {response_data['messages'][0]['id']}")
            return True
        else: print(f"Resposta inesperada API WhatsApp (WA_UTILS): {response_data}"); return False
    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP enviando para {numero_destino} (WA_UTILS): {http_err}")
        print(f"Detalhes erro API (WA_UTILS): {http_err.response.text if http_err.response else 'Sem detalhes'}")
        return False
    except Exception as e: print(f"Outro erro em enviar_mensagem_whatsapp (WA_UTILS): {e}"); return False