from flask import Flask, request, jsonify, g
import json
import config # Importa as configurações globais
from database import init_db as initialize_database, close_db_connection, get_or_create_user # Importa funções do DB, incluindo as novas para usuários
from gemini_handler import extrair_info_gemini, gemini_model # Importa do Gemini Handler
from chatbot_logic import gerar_resposta_do_chatbot # Importa a lógica central do chatbot
from whatsapp_utils import enviar_mensagem_whatsapp # Importa a função de envio do WhatsApp

app = Flask(__name__)
app.teardown_appcontext(close_db_connection) # Registra a função para fechar a conexão com o banco de dados no contexto da aplicação

# --- ROTAS DA API FLASK ---
@app.route('/mensagem_ia_teste', methods=['POST'])
def mensagem_com_ia_teste():
    if not gemini_model: return jsonify({"resposta_agente": "Erro: IA (Gemini) não configurada."}), 500
    
    dados = request.json
    texto_usuario = dados.get('texto')
    if not texto_usuario: return jsonify({"erro": "Nenhum texto fornecido"}), 400
    
    # Para testes diretos, simulamos um ID de usuário e perfil. O fluxo de onboarding completo é melhor testado via WhatsApp. 
    simulated_wa_id = "teste_api_direta_123" # ID de usuário simulado
    # É preciso estar dentro de um contexto de aplicação para usar 'g' e, consequentemente, get_db()
    with app.app_context():
        user_profile = get_or_create_user(simulated_wa_id, "Usuário Teste API")

    if not user_profile: # Checagem caso get_or_create_user retorne None
        return jsonify({"resposta_agente": "Erro ao obter ou criar perfil de usuário para teste."}), 500

    intencao, entidades = extrair_info_gemini(texto_usuario)
    confianca_simulada = 1.0 if intencao else 0.0 # Gemini não fornece confiança de intenção da mesma forma
    
    print(f"Teste - Texto: {texto_usuario}\nIntenção: {intencao}\nEntidades: {entidades}")
    
    # Passa o perfil do usuário simulado para a lógica do chatbot
    r_agente = gerar_resposta_do_chatbot(
        intencao, 
        entidades, 
        texto_usuario, 
        numero_usuario_wa=simulated_wa_id, 
        user_profile=user_profile
    ) 
    
    return jsonify({
        "resposta_agente": r_agente, 
        "intencao_gemini": intencao,
        "confianca_intencao_gemini": confianca_simulada,
        "entidades_gemini": entidades, 
        "texto_original_usuario": texto_usuario
    })

@app.route('/whatsapp_webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET': # Verificação do Webhook pela Meta
        vt_req = request.args.get('hub.verify_token')
        mode = request.args.get('hub.mode')
        challenge = request.args.get('hub.challenge')
        
        print(f"GET Webhook: Mode={mode}, Token Recebido={vt_req}, Challenge={challenge}")
        if mode and vt_req:
            if mode == 'subscribe' and vt_req == config.MEU_VERIFY_TOKEN:
                print("Webhook verificado com sucesso!")
                return challenge, 200
            else: 
                print(f"Falha na verificação. Token esperado: '{config.MEU_VERIFY_TOKEN}', Token recebido: '{vt_req}'")
                return 'Token de verificação não confere ou modo inválido', 403
        else: 
            print("Requisição GET de verificação incompleta.")
            return 'Parâmetros faltando na requisição de verificação', 400

    elif request.method == 'POST': # Recebimento de mensagens do WhatsApp
        data = request.get_json()
        print("\n--- POST WHATSAPP WEBHOOK ---")
        print(json.dumps(data, indent=2)) # Log do payload completo para depuração
        print("---")
        
        if data.get("object") == "whatsapp_business_account":
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        if value.get("messaging_product") == "whatsapp" and "messages" in value:
                            for message_obj in value.get("messages", []):
                                if message_obj.get("type") == "text":
                                    num_wa = message_obj.get("from")
                                    msg_wa = message_obj.get("text", {}).get("body")
                                    user_name_wa = value.get("contacts", [{}])[0].get("profile", {}).get("name", "Usuário")

                                    if msg_wa and num_wa:
                                        print(f"Msg de {user_name_wa} ({num_wa}): '{msg_wa}'")
                                        
                                        # Obter ou criar perfil do usuário e verificar onboarding
                                        user_profile = get_or_create_user(num_wa, user_name_wa)
                                        
                                        if not user_profile: # Segurança adicional
                                            print(f"ERRO APP.PY: Não foi possível obter/criar perfil para {num_wa}")
                                            # Não envie erro para Meta, apenas logue e retorne 200.
                                            break 
                                        
                                        print(f"DEBUG APP.PY: User Profile para {num_wa}: {dict(user_profile)}")

                                        r_user_generated = ""
                                        if not user_profile["onboarding_complete"]:
                                            print(f"Usuário {num_wa} em onboarding. Step: {user_profile['onboarding_step']}")
                                            # Para onboarding, a intenção inicial é nula; msg_wa é a resposta do usuário à pergunta de onboarding.
                                            r_user_generated = gerar_resposta_do_chatbot(None, {}, msg_wa, num_wa, user_profile)
                                        else:
                                            # Onboarding completo, processa normalmente com Gemini
                                            print(f"Usuário {num_wa} com onboarding completo. Processando com Gemini...")
                                            if not gemini_model: 
                                                print("ERRO APP.PY: Cliente Gemini não inicializado.")
                                                # Poderia enviar uma mensagem padrão de erro ao usuário aqui, se desejado
                                                break 
                                            
                                            intencao_wa, entidades_wa = extrair_info_gemini(msg_wa)
                                            r_user_generated = gerar_resposta_do_chatbot(intencao_wa, entidades_wa, msg_wa, num_wa, user_profile)
                                        
                                        print(f"Resposta GERADA para {num_wa}: {r_user_generated}")
                                        if r_user_generated: # Envia resposta se houver alguma
                                            sucesso_envio = enviar_mensagem_whatsapp(num_wa, r_user_generated)
                                            if sucesso_envio: print(f"Resposta enviada OK para {num_wa} no WhatsApp.")
                                            else: print(f"Falha ao enviar resposta para {num_wa} no WhatsApp.")
                                        else:
                                            print(f"Nenhuma resposta gerada para {num_wa} (r_user_generated está vazia ou None).")
                                            
                                else: # Mensagem não é do tipo texto
                                    print(f"Msg não textual de {message_obj.get('from')}, tipo: {message_obj.get('type')}")
                            break # Processa apenas o primeiro objeto 'messages' relevante (geralmente há apenas um)
                return "EVENT_RECEIVED", 200 # Responde 200 OK para a Meta rapidamente
            except Exception as e_main_p: 
                print(f"Erro GRANDE ao processar o POST do webhook: {e_main_p}")
                return "INTERNAL_SERVER_ERROR_IN_PROCESSING", 200 # Ainda retorna 200 para Meta
        else: 
            print("POST recebido no webhook não é do tipo 'whatsapp_business_account'")
            return "NOT_A_WHATSAPP_EVENT", 200
    else: 
        return "Method Not Allowed", 405

# --- INICIALIZAÇÃO DO APP ---
if __name__ == '__main__':
    # Cria o contexto da aplicação para init_db ser chamado corretamente
    with app.app_context():
        initialize_database(app.app_context()) # Passa o contexto da aplicação

    # Prints de aviso sobre configurações ausentes
    if not config.GOOGLE_API_KEY: print("AVISO IMPORTANTE: GOOGLE_API_KEY não está configurado no ambiente.")
    if not config.WHATSAPP_ACCESS_TOKEN: print("AVISO IMPORTANTE: WHATSAPP_ACCESS_TOKEN (para envio) não está configurado.")
    if not config.WHATSAPP_PHONE_NUMBER_ID: print("AVISO IMPORTANTE: WHATSAPP_PHONE_NUMBER_ID (para envio) não está configurado.")
    
    app.run(debug=True, port=5002)