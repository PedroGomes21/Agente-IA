import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, FunctionDeclaration, Tool
import config # Importa as configurações para GOOGLE_API_KEY

gemini_model = None
if config.GOOGLE_API_KEY:
    try:
        genai.configure(api_key=config.GOOGLE_API_KEY)
        gemini_model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        print("Cliente Gemini inicializado com sucesso em gemini_handler.py.")
    except Exception as e:
        print(f"Erro ao inicializar o cliente Gemini em gemini_handler.py: {e}")
        gemini_model = None
else:
    print("ERRO CRÍTICO: GOOGLE_API_KEY não configurada em config.py. Cliente Gemini não inicializado em gemini_handler.py.")

# --- DEFINIÇÃO DAS FERRAMENTAS (FUNÇÕES) PARA O GEMINI ---

avaliar_objetivo_financeiro_tool = FunctionDeclaration(
    name="avaliar_objetivo_financeiro",
    description=("Avalia se o texto do usuário é um objetivo financeiro direto e acionável."),
    parameters={
        "type": "object",
        "properties": {
            "eh_valido": {"type": "boolean", "description": "True se o objetivo for financeiramente direto."},
            "objetivo_reformulado": {"type": "string", "description": "Se inválido, sugira uma reformulação financeira."},
            "feedback_para_usuario": {"type": "string", "description": "Se inválido, forneça uma breve e amigável explicação."}
        },
        "required": ["eh_valido", "objetivo_reformulado"]
    }
)

alterar_renda_mensal_tool = FunctionDeclaration(
    name="alterar_renda_mensal",
    description="Permite que o usuário atualize o valor da sua renda mensal previamente registrada. Frases comuns: 'quero alterar minha renda', 'minha renda mudou para X', 'atualizar renda'.",
    parameters={
        "type": "object",
        "properties": {
            "novo_valor_renda": {
                "type": "number",
                "description": "O novo valor numérico da renda mensal do usuário. Este parâmetro é opcional."
            }
        }
        # A linha "required" foi removida para tornar o parâmetro opcional
    }
)

registrar_gasto_tool = FunctionDeclaration(
    name="registrar_gasto",
    description="Registra uma nova despesa financeira informada pelo usuário. Extrai a descrição, o valor, a categoria e, opcionalmente, a data do gasto.",
    parameters={
        "type": "object",
        "properties": {
            "descricao": {"type": "string", "description": "A descrição detalhada do gasto."},
            "valor": {"type": "number", "description": "O valor numérico do gasto."},
            "categoria": {"type": "string", "description": "A categoria do gasto (ex: Alimentação, Transporte). Inferir se não fornecida."},
            "data": {"type": "string", "description": "A data do gasto. Opcional."}
        },
        "required": ["descricao", "valor", "categoria"]
    }
)

listar_gastos_tool = FunctionDeclaration(
    name="listar_gastos",
    description="Lista os gastos que foram registrados anteriormente pelo usuário.",
    parameters={
        "type": "object",
        "properties": {
            "limite": {"type": "integer", "description": "Opcional. Número máximo de gastos a listar."},
            "periodo": {"type": "string", "description": "Opcional. O período para listar os gastos."}
        }
    }
)

confirmar_operacao_tool = FunctionDeclaration(
    name="confirmar_operacao",
    description="O usuário confirma uma operação anterior (ex: 'sim', 'ok', 'correto').",
    parameters={"type": "object", "properties": {}}
)

cancelar_operacao_tool = FunctionDeclaration(
    name="cancelar_operacao",
    description="O usuário cancela uma operação anterior (ex: 'não', 'cancela', 'errado').",
    parameters={"type": "object", "properties": {}}
)

solicitar_alteracao_gasto_tool = FunctionDeclaration(
    name="solicitar_alteracao_gasto",
    description=("O usuário indica que quer modificar detalhes de um gasto pendente. Pode dizer apenas 'alterar', 'corrigir', ou especificar o campo e o novo valor como 'alterar valor para 50'."),
    parameters={
        "type": "object",
        "properties": {
            "campo_a_alterar": {"type": "string", "description": "O campo a alterar (descrição, valor, categoria, data)."},
            "novo_valor_texto": {"type": "string", "description": "O novo valor para o campo."}
        }
    }
)

consultar_renda_tool = FunctionDeclaration(
    name="consultar_renda",
    description="Permite que o usuário consulte o valor da sua renda mensal registrada.",
    parameters={"type": "object", "properties": {}}
)

# Agrupa as ferramentas que o Gemini pode usar
ferramentas_gemini = Tool(function_declarations=[
    registrar_gasto_tool,
    listar_gastos_tool,
    confirmar_operacao_tool,
    cancelar_operacao_tool,
    solicitar_alteracao_gasto_tool,
    avaliar_objetivo_financeiro_tool,
    alterar_renda_mensal_tool,
    consultar_renda_tool
])

def extrair_info_gemini(texto_usuario):
    """Envia o texto para o Gemini e extrai intenção e entidades."""
    if not gemini_model:
        print("ERRO em extrair_info_gemini: Modelo Gemini não inicializado.")
        return None, {}

    print(f"Enviando para Gemini: '{texto_usuario}'")
    try:
        prompt_com_instrucao = (
            f"Seu objetivo principal é ajudar o usuário chamando uma das funções (tools) disponíveis. "
            f"Se você não conseguir encontrar uma função adequada para o pedido do usuário ou se o pedido for muito vago, "
            f"você DEVE responder diretamente ao usuário em PORTUGUÊS do Brasil, pedindo mais contexto de forma amigável. "
            f"Exemplo: 'Não entendi. Você está tentando registrar um gasto ou alterar sua renda?'.\n\n"
            f"Pedido do usuário: '{texto_usuario}'"
        )

        response = gemini_model.generate_content(
            prompt_com_instrucao,
            tools=[ferramentas_gemini],
            tool_config={"function_calling_config": "AUTO"},
        )
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call.name:
                    intent_name = part.function_call.name
                    entities = dict(part.function_call.args) if part.function_call.args else {}
                    print(f"Gemini chamou função: {intent_name} com args: {entities}")
                    return intent_name, entities
            
            if hasattr(response.candidates[0].content.parts[-1], 'text') and response.candidates[0].content.parts[-1].text:
                text_response_from_gemini = response.candidates[0].content.parts[-1].text
                print(f"Gemini respondeu com texto direto: {text_response_from_gemini}")
                return "resposta_textual_gemini", {"texto_resposta": text_response_from_gemini}
        
        print("Gemini não chamou nenhuma função ou retornou texto claro na estrutura esperada.")
        return None, {}

    except Exception as e:
        print(f"Erro ao comunicar com Gemini ou processar resposta: {e}")
        return None, {}
