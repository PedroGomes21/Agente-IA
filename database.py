import sqlite3
from flask import g
import config

# --- Funções de Conexão com o Banco ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(config.DATABASE_FILENAME)
        db.row_factory = sqlite3.Row
    return db

def close_db_connection(exception=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- Função de Inicialização do Banco de Dados (ATUALIZADA) ---
def init_db(app_context):
    with app_context:
        db = get_db()
        cursor = db.cursor()
        
        # Altera tabela de gastos para incluir o ID do usuário
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wa_id TEXT NOT NULL, 
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                data_despesa TEXT, 
                categoria TEXT, 
                data_registro_sistema TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Altera tabela de usuários para incluir o rastreamento de avisos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                wa_id TEXT PRIMARY KEY,
                nome_perfil TEXT,
                objetivo_financeiro TEXT,
                renda_mensal REAL,
                onboarding_step TEXT,
                onboarding_complete BOOLEAN DEFAULT FALSE,
                ultimo_aviso_orcamento INTEGER DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()
        print(f"Banco de dados '{config.DATABASE_FILENAME}' inicializado. Tabelas 'gastos' e 'usuarios' atualizadas.")

# --- Funções para a tabela GASTOS (ATUALIZADAS) ---

def salvar_gasto_no_banco(wa_id, descricao, valor_gasto, categoria, data_despesa_str=None):
    """Salva um novo gasto, agora vinculado a um usuário (wa_id)."""
    try:
        vf = float(valor_gasto); db = get_db(); c = db.cursor(); ddf = None
        if data_despesa_str:
            try: ddf = data_despesa_str.split('T')[0] if 'T' in data_despesa_str else data_despesa_str
            except Exception as e: print(f"Erro ao formatar data '{data_despesa_str}': {e}")
        
        # Inclui wa_id no INSERT
        c.execute("INSERT INTO gastos (wa_id, descricao, valor, categoria, data_despesa) VALUES (?, ?, ?, ?, ?)",
                  (wa_id, descricao, vf, categoria, ddf))
        db.commit(); print(f"Gasto salvo para {wa_id}: {descricao}, R${vf:.2f}"); return True
    except (ValueError, TypeError): print(f"Erro ao salvar gasto: Valor '{valor_gasto}' inválido."); return False
    except Exception as e: print(f"Erro DB save: {e}"); db.rollback(); return False

def buscar_gastos_do_banco(wa_id, limite=5):
    """Busca os últimos gastos de um usuário específico."""
    gastos_recuperados = [];
    try:
        db = get_db(); c = db.cursor()
        q = "SELECT id, descricao, valor, categoria, data_despesa FROM gastos WHERE wa_id = ? ORDER BY id DESC LIMIT ?"
        c.execute(q, (wa_id, limite,)); resultados = c.fetchall()
        for r in resultados: gastos_recuperados.append(dict(r))
        print(f"Buscados {len(gastos_recuperados)} gastos para {wa_id}."); return gastos_recuperados
    except Exception as e: print(f"Erro DB fetch para {wa_id}: {e}"); return []

def calcular_total_gastos_mes_atual(wa_id):
    """Calcula a soma de todos os gastos de um usuário no mês atual."""
    total = 0.0
    try:
        db = get_db(); cursor = db.cursor()
        # Usa strftime para comparar apenas o ano e o mês ('YYYY-MM')
        # COALESCE é usado para pegar a data_despesa e, se for nula, usar a data_registro_sistema
        query = """
            SELECT SUM(valor)
            FROM gastos
            WHERE wa_id = ? AND strftime('%Y-%m', COALESCE(data_despesa, date(data_registro_sistema))) = strftime('%Y-%m', 'now', 'localtime')
        """
        cursor.execute(query, (wa_id,))
        resultado = cursor.fetchone()
        if resultado and resultado[0] is not None:
            total = float(resultado[0])
        print(f"Total de gastos no mês para {wa_id}: R${total:.2f}")
        return total
    except Exception as e: print(f"Erro ao calcular total de gastos para {wa_id}: {e}"); return total

# --- Funções para a tabela USUARIOS (ATUALIZADAS) ---

def update_ultimo_aviso_orcamento(wa_id, percentual):
    """Atualiza o último percentual de aviso de orçamento enviado para o usuário."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE usuarios SET ultimo_aviso_orcamento = ? WHERE wa_id = ?", (percentual, wa_id))
        db.commit()
        print(f"Usuário {wa_id} atualizado para ultimo_aviso_orcamento: {percentual}%")
        return True
    except Exception as e:
        print(f"Erro ao atualizar ultimo_aviso_orcamento para {wa_id}: {e}")
        db.rollback()
        return False
        
# ... (o restante das funções de usuário: get_or_create_user, get_user_profile, etc., permanecem as mesmas) ...
def get_or_create_user(wa_id, nome_perfil=None):
    db = get_db(); cursor = db.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE wa_id = ?", (wa_id,))
    user_row = cursor.fetchone()
    if user_row is None:
        print(f"Criando novo usuário no BD para wa_id: {wa_id}")
        nome_a_salvar = nome_perfil if nome_perfil and nome_perfil.strip() else "Usuário"
        cursor.execute(
            "INSERT INTO usuarios (wa_id, nome_perfil, onboarding_step, onboarding_complete) VALUES (?, ?, ?, ?)",
            (wa_id, nome_a_salvar, "new_user_welcome", False) 
        )
        db.commit()
        cursor.execute("SELECT * FROM usuarios WHERE wa_id = ?", (wa_id,))
        user_row = cursor.fetchone()
    return dict(user_row) if user_row else None

def get_user_profile(wa_id):
    db = get_db(); cursor = db.cursor(); cursor.execute("SELECT * FROM usuarios WHERE wa_id = ?", (wa_id,)); user_row = cursor.fetchone()
    return dict(user_row) if user_row else None

def update_user_onboarding_step(wa_id, step):
    try:
        db = get_db(); cursor = db.cursor()
        cursor.execute("UPDATE usuarios SET onboarding_step = ? WHERE wa_id = ?", (step, wa_id))
        db.commit(); print(f"Usuário {wa_id} atualizado para onboarding_step: {step}"); return True
    except Exception as e: print(f"Erro ao atualizar onboarding_step para {wa_id}: {e}"); db.rollback(); return False

def update_user_financial_goal(wa_id, goal):
    try:
        db = get_db(); cursor = db.cursor()
        cursor.execute("UPDATE usuarios SET objetivo_financeiro = ? WHERE wa_id = ?", (goal, wa_id))
        db.commit(); print(f"Usuário {wa_id} atualizou objetivo_financeiro para: {goal}"); return True
    except Exception as e: print(f"Erro ao atualizar objetivo_financeiro para {wa_id}: {e}"); db.rollback(); return False

def update_user_monthly_income(wa_id, income_str):
    try:
        income_float = float(income_str) 
        db = get_db(); cursor = db.cursor()
        cursor.execute("UPDATE usuarios SET renda_mensal = ? WHERE wa_id = ?", (income_float, wa_id))
        db.commit(); print(f"Usuário {wa_id} atualizou renda_mensal para: {income_float}"); return True
    except (ValueError, TypeError): print(f"Erro: Renda '{income_str}' inválida."); return False
    except Exception as e: print(f"Erro ao atualizar renda_mensal para {wa_id}: {e}"); db.rollback(); return False

def complete_onboarding_for_user(wa_id):
    try:
        db = get_db(); cursor = db.cursor()
        cursor.execute("UPDATE usuarios SET onboarding_complete = TRUE, onboarding_step = 'complete' WHERE wa_id = ?", (wa_id,))
        db.commit(); print(f"Onboarding concluído para usuário {wa_id}"); return True
    except Exception as e: print(f"Erro ao completar onboarding para {wa_id}: {e}"); db.rollback(); return False
