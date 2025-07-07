import datetime
from database import (
    salvar_gasto_no_banco, 
    buscar_gastos_do_banco,
    update_user_onboarding_step,
    update_user_financial_goal,
    update_user_monthly_income,
    complete_onboarding_for_user,
    get_user_profile,
    calcular_total_gastos_mes_atual,
    update_ultimo_aviso_orcamento
)
from gemini_handler import extrair_info_gemini

# Dicionário para armazenar gastos pendentes de confirmação
gastos_pendentes = {} 

def categorizar_gasto(descricao):
    # Função para categorizar gastos baseada em palavras-chave.
    descricao_lower = descricao.lower()
    mapa_categorias = {
        "Alimentação": ["almoço", "jantar", "café", "lanche", "restaurante", "mercado", "comida", "padaria", "ifood", "rappi", "supermercado"],
        "Transporte": ["uber", "99", "gasolina", "estacionamento", "metrô", "ônibus", "passagem", "combustível", "taxi"],
        "Moradia": ["aluguel", "condomínio", "água", "luz", "internet", "gás", "iptu", "telefone fixo"],
        "Lazer": ["cinema", "show", "bar", "festa", "jogo", "livro", "streaming", "netflix", "spotify", "teatro", "viagem"],
        "Saúde": ["farmácia", "remédio", "consulta", "médico", "hospital", "plano de saúde", "dentista"],
        "Outros": [] 
    }
    for categoria, palavras_chave in mapa_categorias.items():
        for palavra in palavras_chave:
            if palavra in descricao_lower:
                return categoria
    return "Outros"

def checar_e_gerar_aviso_orcamento(numero_usuario_wa):
    """Verifica os gastos do usuário e retorna uma mensagem de aviso se um novo limiar foi atingido."""
    user_profile = get_user_profile(numero_usuario_wa)
    if not user_profile or not user_profile.get("renda_mensal"):
        return None # Não pode checar orçamento sem renda registrada

    renda = user_profile["renda_mensal"]
    if renda <= 0: return None # Evita divisão por zero

    total_gastos = calcular_total_gastos_mes_atual(numero_usuario_wa)
    percentual_gasto = (total_gastos / renda) * 100
    
    ultimo_aviso = user_profile.get("ultimo_aviso_orcamento", 0)
    
    # Limiares de aviso
    limiares = [100, 90, 80, 75, 70, 60, 50]
    
    # Encontra o maior limiar atingido que ainda não foi avisado
    for limiar in limiares:
        if percentual_gasto >= limiar and ultimo_aviso < limiar:
            # Encontramos um novo aviso a ser enviado!
            update_ultimo_aviso_orcamento(numero_usuario_wa, limiar)
            aviso = f"\n\n**Atenção!** 🔔\nVocê já comprometeu **{percentual_gasto:.0f}%** da sua renda de R${renda:.2f} este mês (Total gasto: R${total_gastos:.2f})."
            return aviso
            
    return None # Nenhum novo aviso necessário


def gerar_resposta_do_chatbot(intencao, entidades, texto_usuario_original="", numero_usuario_wa=None, user_profile=None):
    """Processa a intenção e entidades para gerar a resposta do chatbot."""
    resposta_final_agente = "Desculpe, não consegui processar seu pedido agora."

    if not user_profile:
        print(f"ERRO LOGIC: User profile não fornecido para {numero_usuario_wa}")
        return "Desculpe, estou com um problema para acessar suas informações. Tente novamente mais tarde."

    # --- LÓGICA DE ONBOARDING ---
    if not user_profile["onboarding_complete"]:
        # ... (Sua lógica de onboarding como antes)
        current_step = user_profile["onboarding_step"]
        if current_step == "new_user_welcome":
            resposta_final_agente = ("Olá! 👋 Sou seu assistente financeiro pessoal.\n\nPara que eu possa te ajudar da melhor forma, primeiro preciso entender um pouco sobre você.\n\nPara começar, poderia me informar sua *renda mensal aproximada*? (ex: 3000, 4500.50)")
            update_user_onboarding_step(numero_usuario_wa, "awaiting_income")
        elif current_step == "awaiting_income":
            if update_user_monthly_income(numero_usuario_wa, texto_usuario_original):
                update_user_onboarding_step(numero_usuario_wa, "awaiting_goal_after_income")
                resposta_final_agente = ("Ótimo, renda anotada! ✅\n\nAgora, me diga, qual é o seu **principal objetivo financeiro** no momento?\n\nExemplos: guardar dinheiro, começar a investir, criar uma reserva de emergência, etc.")
            else:
                resposta_final_agente = ("Hum, esse valor de renda não parece ser um número. 🤔\nPoderia me informar sua renda mensal aproximada usando apenas números?")
        elif current_step == "awaiting_goal_after_income":
            intencao_validacao, entidades_validacao = extrair_info_gemini(texto_usuario_original)
            if intencao_validacao == 'avaliar_objetivo_financeiro':
                eh_valido = entidades_validacao.get('eh_valido', False)
                objetivo_final = entidades_validacao.get('objetivo_reformulado')
                feedback = entidades_validacao.get('feedback_para_usuario')
                if eh_valido and objetivo_final:
                    update_user_financial_goal(numero_usuario_wa, objetivo_final)
                    complete_onboarding_for_user(numero_usuario_wa)
                    updated_user_profile = get_user_profile(numero_usuario_wa)
                    renda = updated_user_profile.get('renda_mensal', 0)
                    resposta_final_agente = (f"Perfeito! Onboarding concluído. 👍\n\nSeu objetivo: **{objetivo_final}**\nSua renda: **R${renda:.2f}**\n\nAgora você já pode usar todas as funcionalidades. Como posso te ajudar hoje?")
                else:
                    resposta_final_agente = f"{feedback} Por favor, tente descrever seu objetivo novamente com um foco mais financeiro."
            else:
                resposta_final_agente = "Não entendi bem seu objetivo. Poderia tentar descrevê-lo de forma mais direta? (ex: 'guardar dinheiro para uma viagem')"
        else:
             resposta_final_agente = f"Passo de onboarding inesperado: '{current_step}'. Como posso ajudar?"
             complete_onboarding_for_user(numero_usuario_wa)
        return resposta_final_agente

    # --- LÓGICA PRINCIPAL DO CHATBOT (APÓS ONBOARDING) ---
    
    if intencao == 'registrar_gasto':
        # ... (Sua lógica de registrar_gasto e pedir confirmação permanece a mesma)
        valor_extraido = entidades.get('valor'); descricao_extraida = entidades.get('descricao')
        categoria_sugerida = entidades.get('categoria', 'Outros'); data_str_gemini = entidades.get('data')
        if valor_extraido is not None and descricao_extraida:
            try:
                valor_float = float(valor_extraido); data_atual_string = datetime.date.today().strftime("%Y-%m-%d")
                data_para_salvar = data_atual_string; data_exibir = f"hoje ({data_atual_string})"
                if data_str_gemini:
                    data_para_salvar = data_str_gemini.split('T')[0] if 'T' in data_str_gemini else data_str_gemini
                    data_exibir = data_para_salvar
                categoria_final = categoria_sugerida if categoria_sugerida != 'Outros' else categorizar_gasto(descricao_extraida)
                gastos_pendentes[numero_usuario_wa] = {"descricao": descricao_extraida, "valor": valor_float, "categoria": categoria_final, "data_para_salvar": data_para_salvar}
                msg_confirmacao = (f"Registrando:\n- Desc: {descricao_extraida}\n- Valor: R${valor_float:.2f}\n- Cat: {categoria_final}\n- Data: {data_exibir}\n")
                if not data_str_gemini: msg_confirmacao += f"(Como não especificou a data, usaremos data de hoje: {data_atual_string}).\n"
                msg_confirmacao += "\nCerto? (sim/não/alterar)"; resposta_final_agente = msg_confirmacao
            except (ValueError, TypeError): resposta_final_agente = f"Descrição '{descricao_extraida}', mas o valor '{valor_extraido}' parece inválido."
        elif not valor_extraido: resposta_final_agente = "Não identifiquei o valor do gasto."
        elif not descricao_extraida: resposta_final_agente = "Não identifiquei a descrição do gasto."
        else: resposta_final_agente = "Não consegui pegar todos os detalhes do gasto."

    elif intencao == 'confirmar_operacao':
        if numero_usuario_wa and numero_usuario_wa in gastos_pendentes:
            gasto_a_salvar = gastos_pendentes.pop(numero_usuario_wa)
            if salvar_gasto_no_banco(numero_usuario_wa, gasto_a_salvar['descricao'],gasto_a_salvar['valor'],gasto_a_salvar['categoria'],gasto_a_salvar['data_para_salvar']):
                resposta_final_agente = (f"Confirmado! Gasto salvo com sucesso.")
                
                aviso_orcamento = checar_e_gerar_aviso_orcamento(numero_usuario_wa)
                if aviso_orcamento:
                    resposta_final_agente += aviso_orcamento
            else: 
                resposta_final_agente = "Ok, mas ocorreu um erro ao salvar. Por favor, tente registrar novamente."
        else: 
            resposta_final_agente = "Não tenho nenhum gasto pendente para confirmar."
    
    elif intencao == 'listar_gastos':
        limite_usr = entidades.get('limite', 5); limite_int = 5
        try: limite_int = int(limite_usr)
        except (ValueError, TypeError): pass
        gastos_recentes = buscar_gastos_do_banco(numero_usuario_wa, limite=limite_int)
        if gastos_recentes:
            rfa = "Últimos gastos registrados:\n"
            for g_item in gastos_recentes:
                cat_info = f" (Cat: {g_item['categoria']})" if g_item['categoria'] else ""
                dex = g_item['data_despesa'] if g_item['data_despesa'] else str(g_item['data_registro_sistema']).split(" ")[0]
                vfor = f"{g_item['valor']:.2f}" if isinstance(g_item['valor'],(int,float)) else g_item['valor']
                rfa += f"- R${vfor} em '{g_item['descricao']}'{cat_info} (Data: {dex})\n"
            resposta_final_agente = rfa.strip()
        else: 
            resposta_final_agente = "Nenhum gasto registrado."
            
    # <<< BLOCO ADICIONADO PARA ALTERAR A RENDA >>>
    elif intencao == 'alterar_renda_mensal':
        if not user_profile["onboarding_complete"]:
            resposta_final_agente = "Vamos primeiro concluir sua configuração inicial. Por favor, me informe sua renda mensal para continuarmos."
            update_user_onboarding_step(numero_usuario_wa, "awaiting_income")
        else:
            novo_valor = entidades.get('novo_valor_renda')
            if novo_valor is not None:
                if update_user_monthly_income(numero_usuario_wa, novo_valor):
                    try:
                        valor_formatado = f"{float(novo_valor):.2f}"
                        resposta_final_agente = f"Entendido! Sua renda mensal foi atualizada com sucesso para R${valor_formatado}."
                    except (ValueError, TypeError):
                        resposta_final_agente = f"Entendido! Sua renda mensal foi atualizada para '{novo_valor}'."
                else:
                    resposta_final_agente = f"Ocorreu um erro ao tentar atualizar sua renda. O valor '{novo_valor}' parece ser inválido."
            else:
                resposta_final_agente = "Entendi que você quer alterar sua renda, mas não consegui identificar o novo valor. Poderia tentar de novo, por exemplo: 'alterar minha renda para 5000'?"

    # ... (O restante das suas intenções: cancelar_operacao, solicitar_alteracao_gasto, etc., permanecem as mesmas)
    # Colocando os outros elifs aqui para garantir que a ordem esteja correta
    elif intencao == 'cancelar_operacao':
        if numero_usuario_wa and numero_usuario_wa in gastos_pendentes:
            gastos_pendentes.pop(numero_usuario_wa)
            resposta_final_agente = "Ok, registro cancelado."
        else: resposta_final_agente = "Ok, não havia nada pendente para cancelar."
            
    elif intencao == 'solicitar_alteracao_gasto':
        if numero_usuario_wa and numero_usuario_wa in gastos_pendentes:
            gasto_atual = gastos_pendentes[numero_usuario_wa]
            campo_a_alterar = entidades.get('campo_a_alterar',"").lower(); novo_valor_texto = entidades.get('novo_valor_texto')
            if campo_a_alterar and novo_valor_texto:
                alterado = False
                if "descri" in campo_a_alterar: gasto_atual['descricao'] = novo_valor_texto; gasto_atual['categoria'] = categorizar_gasto(novo_valor_texto); alterado = True
                elif "valor" in campo_a_alterar:
                    try: gasto_atual['valor'] = float(novo_valor_texto); alterado = True
                    except (ValueError, TypeError): return f"'{novo_valor_texto}' não é um valor válido. O gasto não foi alterado."
                elif "categ" in campo_a_alterar: gasto_atual['categoria'] = novo_valor_texto; alterado = True
                elif "data" in campo_a_alterar: gasto_atual['data_para_salvar'] = novo_valor_texto.split('T')[0] if 'T' in novo_valor_texto else novo_valor_texto; alterado = True
                if alterado:
                    gastos_pendentes[numero_usuario_wa] = gasto_atual
                    resposta_final_agente = (f"Ok, alterado. Gasto atualizado:\n- Desc: {gasto_atual['descricao']}\n- Valor: R${gasto_atual['valor']:.2f}\n- Cat: {gasto_atual['categoria']}\n- Data: {gasto_atual['data_para_salvar']}\n\nCerto agora? (sim/alterar/cancelar)")
                else: resposta_final_agente = f"Não entendi qual campo ('{campo_a_alterar}') você quer alterar."
            else:
                resposta_final_agente = (f"Quer alterar o quê no gasto pendente?\n(Desc: {gasto_atual['descricao']}, Valor: R${gasto_atual['valor']:.2f}, Cat: {gasto_atual['categoria']}, Data: {gasto_atual['data_para_salvar']})\nDiga, ex: 'alterar valor para 30'.")
        else: resposta_final_agente = "Não tenho nenhum gasto pendente para alterar."
    
    elif intencao == 'consultar_renda':
        if user_profile and user_profile["onboarding_complete"]:
            renda_registrada = user_profile.get('renda_mensal')
            if renda_registrada is not None:
                resposta_final_agente = f"Sua renda mensal registrada atualmente é de R${renda_registrada:.2f}."
            else:
                resposta_final_agente = "Você ainda não registrou uma renda. Para fazer isso, diga 'alterar minha renda para [valor]'."
        else:
            resposta_final_agente = "Para que eu possa te informar sua renda, primeiro precisamos concluir sua configuração inicial. Por favor, me diga sua renda mensal para continuarmos."
            update_user_onboarding_step(numero_usuario_wa, "awaiting_income")

    elif intencao == "resposta_textual_gemini" and entidades.get("texto_resposta"):
        resposta_final_agente = entidades["texto_resposta"]
    elif intencao: 
        resposta_final_agente = f"Entendi a intenção '{intencao}', mas ainda não estou programado para lidar com ela."
    else:
        if user_profile and not user_profile["onboarding_complete"]:
             if user_profile["onboarding_step"] == "awaiting_goal_after_income": resposta_final_agente = "Ainda estou aguardando seu objetivo financeiro. Poderia me dizer qual é?"
             elif user_profile["onboarding_step"] == "awaiting_income": resposta_final_agente = "Ainda estou aguardando sua renda mensal. Poderia me informar?"
             else: resposta_final_agente = "Não entendi bem. Poderia tentar de outra forma?"
        else:
            resposta_final_agente = "Desculpe, não entendi o que você quis dizer. Pode tentar de outra forma?"
    
    return resposta_final_agente
