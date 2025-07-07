from flask import Flask, request, jsonify, g 
import google.generativeai as genai # Adicionado para Gemini
from google.generativeai.types import HarmCategory, HarmBlockThreshold, FunctionDeclaration, Tool # Para definir as ferramentas do Gemini
import os 
import sqlite3
import json 
import requests
import datetime 

# --- CONFIGURAÇÕES GLOBAIS ---
MEU_VERIFY_TOKEN = "codigotestedoagenteiawebhook" # Seu verify token do webhook WhatsApp. MUDE PARA ALGO SEGURO!

# Carregando variáveis de ambiente
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_GRAPH_API_VERSION = "v19.0" # Use uma versão estável da API Graph (ex: v19.0, v20.0)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- DEBUG PRINTS INICIAIS ---
print("--- INICIALIZANDO SCRIPT app.py ---")
print(f"DEBUG GLOBAL (ao iniciar): MEU_VERIFY_TOKEN = {MEU_VERIFY_TOKEN}")
print(f"DEBUG GLOBAL (ao iniciar): WHATSAPP_TOKEN presente? {'Sim' if WHATSAPP_TOKEN else 'NÃO'}")
print(f"DEBUG GLOBAL (ao iniciar): WHATSAPP_PHONE_NUMBER_ID presente? {'Sim' if WHATSAPP_PHONE_NUMBER_ID else 'NÃO'}")
print(f"DEBUG GLOBAL (ao iniciar): GOOGLE_API_KEY presente? {'Sim' if GOOGLE_API_KEY else 'NÃO'}")
# --- FIM DEBUG PRINTS INICIAIS ---

app = Flask(__name__)

# --- CONFIGURAÇÃO DO BANCO DE DADOS SQLITE ---
DATABASE = 'meus_gastos.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                data_despesa TEXT, 
                categoria TEXT,  -- <<< ADICIONE ESTA LINHA
                data_registro_sistema TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        print("Banco de dados inicializado e tabela 'gastos' (com categoria) verificada/criada.")
# --- CONFIGURAÇÃO DO CLIENTE GEMINI ---
gemini_model = None
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        gemini_model = genai.GenerativeModel(
            'gemini-1.5-flash-latest', # Modelo rápido e custo-efetivo
            # safety_settings ajustado para ser um dicionário de HarmCategory para HarmBlockThreshold
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        print("Cliente Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar o cliente Gemini: {e}")
        gemini_model = None
else:
    print("ERRO CRÍTICO: Variável GOOGLE_API_KEY não configurada. Cliente Gemini não inicializado.")

# --- DEFINIÇÃO DAS FERRAMENTAS (FUNÇÕES) PARA O GEMINI ---
registrar_gasto_tool = FunctionDeclaration(
    name="registrar_gasto",
    description="Registra uma nova despesa financeira informada pelo usuário. Extrai a descrição, o valor, a categoria e, opcionalmente, a data do gasto.",
    parameters={
        "type": "object",
        "properties": {
            "descricao": {"type": "string", "description": "A descrição detalhada do gasto (ex: almoço no restaurante X, conta de luz)"},
            "valor": {"type": "number", "description": "O valor numérico do gasto."},
            "categoria": {"type": "string", "description": "A categoria do gasto (ex: Alimentação, Transporte, Moradia, Lazer, Saúde, Educação, Outros). Inferir se não fornecida."},
            "data": {"type": "string", "description": "A data em que o gasto ocorreu. Pode ser relativa (ex: 'hoje', 'ontem') ou específica (ex: '25 de dezembro'). Opcional, se não informada, usar data atual."}
        },
        "required": ["descricao", "valor", "categoria"] # Categoria agora é requerida pela IA
    }
)

listar_gastos_tool = FunctionDeclaration(
    name="listar_gastos",
    description="Lista os gastos que foram registrados anteriormente pelo usuário.",
    parameters={ "type": "object", "properties": {
            "limite": {"type": "integer", "description": "Opcional. Número máximo de gastos a serem listados, padrão 5."}
        }
    }
)

ferramentas_gemini = Tool(function_declarations=[
    registrar_gasto_tool,
    listar_gastos_tool
])

# --- FUNÇÕES AUXILIARES ---
def extrair_info_gemini(texto_usuario):
    if not gemini_model:
        print("ERRO: Modelo Gemini não inicializado ao tentar extrair info.")
        return None, {}
    print(f"Enviando para Gemini: '{texto_usuario}'")
    try:
        response = gemini_model.generate_content(
            texto_usuario,
            tools=[ferramentas_gemini],
            tool_config={"function_calling_config": "AUTO"},
            # safety_settings já está no modelo
        )
        # print(f"Resposta Bruta do Gemini: {response}") # Log mais detalhado da resposta completa
        
        if response.candidates and response.candidates[0].content.parts:
            # Prioriza function call
            for part in response.candidates[0].content.parts: # Itera pelas partes
                if part.function_call.name: # Verifica se existe function_call e se tem nome
                    intent_name = part.function_call.name
                    entities = dict(part.function_call.args) if part.function_call.args else {}
                    print(f"Gemini chamou função: {intent_name} com args: {entities}")
                    return intent_name, entities

            # Se não houve function call, verifica se há texto na resposta
            if response.candidates[0].text:
                 print(f"Gemini respondeu com texto: {response.candidates[0].text}")
                 # Poderia tentar uma intenção padrão ou tratar como "não entendido"
                 return "resposta_textual_gemini", {"texto_resposta": response.candidates[0].text}
        
        print("Gemini não chamou nenhuma função ou retornou texto claro.")
        return None, {}

    except Exception as e:
        print(f"Erro ao comunicar com Gemini ou processar resposta: {e}")
        # print(f"Detalhes do erro Gemini: {getattr(e, 'response', '')}") # Para erros de API
        return None, {}

def salvar_gasto_no_banco(descricao, valor_gasto, categoria, data_despesa_str=None): # Adicionada categoria
    try:
        vf = float(valor_gasto); db = get_db(); c = db.cursor(); ddf = None
        if data_despesa_str:
            try: ddf = data_despesa_str.split('T')[0] if 'T' in data_despesa_str else data_despesa_str
            except Exception as e: print(f"Erro ao formatar data '{data_despesa_str}': {e}")
        c.execute("INSERT INTO gastos (descricao, valor, categoria, data_despesa) VALUES (?, ?, ?, ?)", # Adicionada categoria
                  (descricao, vf, categoria, ddf))
        db.commit(); print(f"Gasto salvo: {descricao}, R${vf:.2f}, Categoria: {categoria}, Data: {ddf}"); return True
    except ValueError: print(f"Erro: Valor '{valor_gasto}' não é número."); return False
    except Exception as e: print(f"Erro DB save: {e}"); db.rollback(); return False

def buscar_gastos_do_banco(limite=5):
    gr = [];
    try:
        db = get_db(); c = db.cursor()
        # Adicionada categoria à query
        q = "SELECT id, descricao, valor, categoria, data_despesa, data_registro_sistema FROM gastos ORDER BY id DESC LIMIT ?"
        c.execute(q, (limite,)); resultados = c.fetchall()
        for r in resultados: gr.append(dict(r))
        print(f"Buscados {len(gr)} gastos."); return gr
    except Exception as e: print(f"Erro DB fetch: {e}"); return []

# --- FUNÇÃO CENTRAL DE LÓGICA DO CHATBOT ---
def gerar_resposta_do_chatbot(intencao, entidades, texto_usuario_original="", numero_usuario_wa=None):
    resposta_final_agente = "Desculpe, não consegui processar seu pedido agora."

    if intencao == 'registrar_gasto':
        valor_extraido = entidades.get('valor')
        descricao_extraida = entidades.get('descricao')
        categoria_extraida = entidades.get('categoria', 'Outros') # Pega categoria ou usa 'Outros'
        data_gasto_str = entidades.get('data')
        
        if valor_extraido is not None and descricao_extraida:
            try:
                valor_float = float(valor_extraido)
                if salvar_gasto_no_banco(descricao_extraida, valor_float, categoria_extraida, data_gasto_str):
                    rfa = f"Gasto de R${valor_float:.2f} em '{descricao_extraida}' (categoria: {categoria_extraida}) salvo!"
                    if data_gasto_str:
                        try: 
                            df = data_gasto_str.split('T')[0] if 'T' in data_gasto_str else data_gasto_str
                            rfa += f" (Data: {df})."
                        except: rfa += f" (Data: {data_gasto_str})."
                    resposta_final_agente = rfa
                else: resposta_final_agente = "Entendi o gasto, mas tive um problema ao salvar no banco."
            except ValueError: resposta_final_agente = f"Descrição '{descricao_extraida}', mas o valor '{valor_extraido}' parece inválido."
        elif not valor_extraido: resposta_final_agente = "Não identifiquei o valor do gasto."
        elif not descricao_extraida: resposta_final_agente = "Não identifiquei a descrição do gasto."
        else: resposta_final_agente = "Não consegui pegar todos os detalhes do gasto."
    
    elif intencao == 'listar_gastos': 
        limite_usr = entidades.get('limite', 5)
        try: limite_int = int(limite_usr)
        except: limite_int = 5
        gastos_recentes = buscar_gastos_do_banco(limite=limite_int)
        if gastos_recentes:
            rfa = "Últimos gastos registrados:\n"
            for g_item in gastos_recentes:
                cat_info = f" (Tipo: {g_item['categoria']})\n" if g_item['categoria'] else ""
                dex = g_item['data_despesa'] if g_item['data_despesa'] else str(g_item['data_registro_sistema']).split(" ")[0]
                vfor = f"{g_item['valor']:.2f}" if isinstance(g_item['valor'],(int,float)) else g_item['valor']
                rfa += f"- R${vfor} em '{g_item['descricao']}'{cat_info}    (Data: {dex})\n\n"
            resposta_final_agente = rfa.strip()
        else: resposta_final_agente = "Nenhum gasto registrado."

    elif intencao == "resposta_textual_gemini" and entidades.get("texto_resposta"):
        resposta_final_agente = entidades["texto_resposta"]
    elif intencao: 
        resposta_final_agente = f"Entendi a intenção '{intencao}', mas ainda não estou programado para isso."
    else: # intencao é None
        resposta_final_agente = "Desculpe, não entendi o que você quis dizer. Pode tentar de outra forma?"

    return resposta_final_agente

# --- FUNÇÃO PARA ENVIAR MENSAGEM WHATSAPP ---
def enviar_mensagem_whatsapp(numero_destino, mensagem_texto):
    # ... (função enviar_mensagem_whatsapp permanece a mesma da versão anterior)
    print(f"DEBUG: Entrou na função enviar_mensagem_whatsapp para {numero_destino}")
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print(f"ERRO DENTRO DE enviar_mensagem_whatsapp: Token ou ID não configurados.")
        print(f"DEBUG: WHATSAPP_TOKEN='{WHATSAPP_TOKEN}', WHATSAPP_PHONE_NUMBER_ID='{WHATSAPP_PHONE_NUMBER_ID}'")
        return False
    url = f"https://graph.facebook.com/{WHATSAPP_GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": numero_destino, "type": "text", "text": {"body": mensagem_texto}}
    print(f"DEBUG: Enviando para URL: {url}, Payload: {json.dumps(payload)}")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"DEBUG: Status Code da Meta: {response.status_code}")
        response.raise_for_status()
        response_data = response.json()
        print(f"Resposta API WhatsApp: {json.dumps(response_data, indent=2)}")
        if response_data.get("messages") and response_data["messages"][0].get("id"):
            print(f"Mensagem enviada OK para {numero_destino}. ID: {response_data['messages'][0]['id']}")
            return True
        else: print(f"Resposta inesperada API WhatsApp: {response_data}"); return False
    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP enviando para {numero_destino}: {http_err}")
        print(f"Detalhes erro API: {http_err.response.text if http_err.response else 'Sem detalhes'}")
        return False
    except Exception as e: print(f"Outro erro em enviar_mensagem_whatsapp: {e}"); return False

# --- ROTAS DA API FLASK ---
@app.route('/mensagem_ia_teste', methods=['POST']) # Rota para testes via Postman/curl
def mensagem_com_ia_teste(): # Nome da função atualizado
    if not gemini_model: return jsonify({"resposta_agente": "Erro: IA (Gemini) não configurada."}), 500
    dados = request.json; texto_usuario = dados.get('texto')
    if not texto_usuario: return jsonify({"erro": "Nenhum texto fornecido"}), 400
    
    intencao, entidades = extrair_info_gemini(texto_usuario)
    confianca_simulada = 1.0 if intencao else 0.0
    
    print(f"Teste - Texto: {texto_usuario}\nIntenção: {intencao}\nEntidades: {entidades}")
    r_agente = gerar_resposta_do_chatbot(intencao, entidades, texto_usuario, numero_usuario_wa=None) 
    return jsonify({"resposta_agente":r_agente,"intencao_gemini":intencao,"confianca_intencao_gemini":confianca_simulada,"entidades_gemini":entidades,"texto_original_usuario":texto_usuario})

@app.route('/whatsapp_webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        # ... (lógica GET como antes)
        vt_req = request.args.get('hub.verify_token'); mode = request.args.get('hub.mode'); challenge = request.args.get('hub.challenge')
        print(f"GET Webhook: Mode={mode}, Token={vt_req}, Challenge={challenge}")
        if mode and vt_req:
            if mode == 'subscribe' and vt_req == MEU_VERIFY_TOKEN:
                print("Webhook verificado com sucesso!"); return challenge, 200
            else: print(f"Falha verificação. Token esperado: '{MEU_VERIFY_TOKEN}' Token recebido: '{vt_req}'"); return 'Token/modo inválido', 403
        else: print("Requisição GET incompleta."); return 'Parâmetros faltando', 400
    elif request.method == 'POST':
        data = request.get_json()
        print("\n--- POST WHATSAPP WEBHOOK ---"); print(json.dumps(data, indent=2)); print("---")
        if data.get("object") == "whatsapp_business_account":
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        if value.get("messaging_product") == "whatsapp" and "messages" in value:
                            for message in value.get("messages", []):
                                if message.get("type") == "text":
                                    num_wa = message.get("from"); msg_wa = message.get("text", {}).get("body")
                                    if msg_wa and num_wa:
                                        print(f"Msg de {num_wa}: '{msg_wa}'")
                                        if not gemini_model: print("ERRO: Cliente Gemini não init."); break
                                        
                                        intencao_wa, entidades_wa = extrair_info_gemini(msg_wa)
                                        r_user = gerar_resposta_do_chatbot(intencao_wa, entidades_wa, msg_wa, num_wa)
                                        
                                        print(f"Resposta GERADA para {num_wa}: {r_user}")
                                        if r_user:
                                            sucesso_envio = enviar_mensagem_whatsapp(num_wa, r_user)
                                            if sucesso_envio: print(f"Resposta enviada OK para {num_wa} no WhatsApp.")
                                            else: print(f"Falha ao enviar resposta para {num_wa} no WhatsApp.")
                                else: print(f"Msg não textual de {message.get('from')}, tipo: {message.get('type')}")
                            break 
                return "EVENT_RECEIVED", 200
            except Exception as e_main_p: print(f"Erro GRANDE no POST webhook: {e_main_p}"); return "ERROR_PROC_EVENT", 200
        else: print("POST não é 'whatsapp_business_account'"); return "NOT_WHATSAPP", 200
    else: return "Method Not Allowed", 405

# --- FUNÇÃO DE CATEGORIZAÇÃO (SIMPLES) ---
def categorizar_gasto(descricao):
    # ... (função categorizar_gasto como antes) ...
    descricao_lower = descricao.lower()
    mapa_categorias = {
        "Alimentação": ["almoço", "jantar", "café", "lanche", "restaurante", "mercado", "comida", "padaria", "ifood", "rappi", "supermercado"],
        "Transporte": ["uber", "99", "gasolina", "estacionamento", "metrô", "ônibus", "passagem", "combustível", "taxi"],
        "Moradia": ["aluguel", "condomínio", "água", "luz", "internet", "gás", "iptu", "telefone fixo"],
        "Lazer": ["cinema", "show", "bar", "festa", "jogo", "livro", "streaming", "netflix", "spotify", "teatro", "viagem"],
        "Saúde": ["farmácia", "remédio", "consulta", "médico", "hospital", "plano de saúde", "dentista"],
        "Educação": ["curso", "escola", "faculdade", "material escolar", "palestra"],
        "Vestuário": ["roupa", "calçado", "acessório", "sapatos"],
        "Cuidados Pessoais": ["salão", "barbeiro", "cosméticos", "perfume"],
        "Presentes/Doações": ["presente", "doação"],
        "Investimentos/Poupança": ["investimento", "poupança", "aplicação"],
        "Outros": [] 
    }
    for categoria, palavras_chave in mapa_categorias.items():
        for palavra in palavras_chave:
            if palavra in descricao_lower:
                return categoria
    return "Outros"

# --- INICIALIZAÇÃO DO APP ---
if __name__ == '__main__':
    init_db() 
    if not GOOGLE_API_KEY: print("AVISO: GOOGLE_API_KEY não configurado.")
    if not WHATSAPP_TOKEN: print("AVISO: WHATSAPP_TOKEN (para envio) não config.")
    if not WHATSAPP_PHONE_NUMBER_ID: print("AVISO: WHATSAPP_PHONE_NUMBER_ID (para envio) não config.")
    
    app.run(debug=True, port=5002)