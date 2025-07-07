import os

# Token de Verificação do Webhook do WhatsApp (escolha sua string secreta)
MEU_VERIFY_TOKEN = "codigotestedoagenteiawebhook" # MUDE PARA UM VALOR SEGURO E ÚNICO

# Chave de API do Google para o Gemini
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Credenciais para enviar mensagens via WhatsApp Cloud API
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_GRAPH_API_VERSION = "v19.0" # Use uma versão estável (ex: v19.0, v20.0)

# Configurações do Banco de Dados
DATABASE_FILENAME = 'meus_gastos.db'

# Debug Prints para verificar se as variáveis de ambiente foram carregadas
print("--- CONFIG.PY CARREGADO ---")
print(f"MEU_VERIFY_TOKEN: {MEU_VERIFY_TOKEN}")
print(f"GOOGLE_API_KEY presente? {'Sim' if GOOGLE_API_KEY else 'NÃO'}")
print(f"WHATSAPP_ACCESS_TOKEN presente? {'Sim' if WHATSAPP_ACCESS_TOKEN else 'NÃO'}")
print(f"WHATSAPP_PHONE_NUMBER_ID presente? {'Sim' if WHATSAPP_PHONE_NUMBER_ID else 'NÃO'}")