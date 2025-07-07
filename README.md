# Agente Financeiro IA para WhatsApp

![Status do Projeto](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Linguagem](https://img.shields.io/badge/linguagem-Python-blue)
![Framework](https://img.shields.io/badge/framework-Flask-black)
![IA](https://img.shields.io/badge/IA-Google%20Gemini-orange)

--

## 🤖 Sobre o Projeto

O **Agente Financeiro IA** é um chatbot para WhatsApp projetado para ser seu assistente pessoal de finanças. O objetivo é simplificar o controle de gastos e o planejamento financeiro através de uma interface de conversa natural (Whastapp) e inteligente. Em vez de planilhas complexas, você pode simplesmente "conversar" com seu dinheiro.

Este projeto nasceu da necessidade de uma ferramenta intuitiva que não apenas registra despesas, mas também ajuda os usuários a entenderem seus hábitos financeiros, definirem metas e receberem insights proativos para alcançar seus objetivos.

--

## ✨ Funcionalidades Principais

Atualmente, o assistente já é capaz de:

* **Onboarding Personalizado:** Conduz uma conversa inicial com novos usuários para coletar informações essenciais como renda mensal e objetivo financeiro.
* **Registro Inteligente de Gastos:** Entende frases como "gastei 50 reais com almoço hoje" ou "anota 30 na farmácia".
* **Categorização Automática:** Utiliza IA para sugerir e atribuir categorias aos gastos (ex: Alimentação, Transporte, Lazer).
* **Fluxo de Confirmação e Alteração:** Antes de salvar um gasto, o bot pede confirmação e permite que o usuário altere a descrição, o valor, a categoria ou a data.
* **Consulta de Gastos:** O usuário pode pedir para ver seus últimos lançamentos.
* **Gerenciamento de Renda:** Permite que o usuário registre, consulte e atualize sua renda mensal.
* **Avisos de Orçamento:** Notifica o usuário proativamente quando seus gastos atingem certos percentuais (50%, 75%, 90%, etc.) da sua renda.

--

## 🛠️ Arquitetura e Como Funciona

O projeto é construído sobre uma arquitetura modular que integra diferentes serviços e tecnologias:

1.  **Interface do Usuário:** **WhatsApp**, utilizando a **API Oficial da Meta (Cloud API)**.
2.  **Gateway de Mensagens:** Um webhook público (criado com **ngrok** para desenvolvimento) recebe as mensagens do WhatsApp.
3.  **Backend:** Um servidor web construído com **Flask** (Python) que atua como o cérebro do sistema. Ele gerencia as requisições, o estado da conversa e a lógica de negócios.
4.  **Processamento de Linguagem Natural (NLU):** As mensagens do usuário são enviadas para a **API do Google Gemini**. Usando a funcionalidade de "Tools" (Function Calling), o Gemini identifica a **intenção** do usuário (ex: `registrar_gasto`, `listar_gastos`) e extrai as **entidades** (ex: valor, descrição, categoria).
5.  **Lógica do Chatbot:** Um módulo central (`chatbot_logic.py`) contém a "máquina de estados" que gerencia o fluxo da conversa, como o processo de onboarding, a confirmação de gastos e a geração das respostas.
6.  **Banco de Dados:** Um banco de dados **SQLite** armazena de forma persistente todas as informações dos usuários, seus gastos, renda e objetivos.

--

## 🚀 Tecnologias Utilizadas

* **Linguagem:** Python 3
* **Framework Backend:** Flask
* **Inteligência Artificial (NLU):** Google Gemini API (com Function Calling)
* **Banco de Dados:** SQLite 3
* **Comunicação com APIs Externas:** Biblioteca `requests`
* **Interface:** WhatsApp Cloud API
* **Túnel de Desenvolvimento:** ngrok

--

## 📂 Estrutura do Projeto

O código é organizado em módulos para facilitar a manutenção e escalabilidade:


.


├── app.py                  # Arquivo principal: inicializa o Flask e define as rotas.


├── chatbot_logic.py        # Contém a lógica central e a "máquina de estados" da conversa.


├── config.py               # Centraliza todas as configurações e chaves de API.


├── database.py             # Gerencia a conexão e as operações com o banco de dados SQLite.


├── gemini_handler.py       # Lida com a comunicação com a API do Gemini e a definição de "tools".


├── whatsapp_utils.py       # Contém a função para enviar mensagens de volta para o WhatsApp.


├── requirements.txt        # Lista de dependências Python.


├── .gitignore              # Arquivos e pastas a serem ignorados pelo Git.


└── README.md               # Este arquivo.


--

## ⚙️ Configuração e Instalação Local

Para rodar este projeto localmente, siga os passos abaixo:

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
    cd seu-repositorio
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Nota: Certifique-se de que seu `requirements.txt` contém `flask`, `google-generativeai`, `requests`)*

4.  **Configure as Variáveis de Ambiente:**
    * Este projeto utiliza um arquivo `launch.json` no VS Code para desenvolvimento. Configure as seguintes variáveis de ambiente com suas chaves:
        * `GOOGLE_API_KEY`: Sua chave de API do Google AI Studio.
        * `WHATSAPP_ACCESS_TOKEN`: Seu token de acesso (temporário ou de sistema) da API do WhatsApp.
        * `WHATSAPP_PHONE_NUMBER_ID`: O ID do seu número de telefone da API do WhatsApp.

5.  **Inicialize o Banco de Dados:**
    * Ao rodar o `app.py` pela primeira vez, o banco de dados `meus_gastos.db` será criado automaticamente.

6.  **Execute o Servidor Flask:**
    ```bash
    python app.py
    ```
    O servidor estará rodando em `http://127.0.0.1:5002`.

7.  **Exponha seu Servidor com `ngrok`:**
    * Em um novo terminal, execute:
        ```bash
        ngrok http 5002
        ```
    * Copie o URL HTTPS fornecido pelo `ngrok`.

8.  **Configure o Webhook na Meta for Developers:**
    * No painel do seu aplicativo Meta, vá para a configuração do webhook do WhatsApp.
    * Use o URL do `ngrok` + `/whatsapp_webhook` como o "URL de Retorno de Chamada".
    * Use o seu `MEU_VERIFY_TOKEN` (definido em `config.py`) como o "Token de Verificação".
    * Inscreva-se no campo de webhook **`messages`**.

--

## 🔮 Próximos Passos (Roadmap)

O futuro deste projeto é brilhante! Algumas funcionalidades planejadas incluem:

-   [ ] **Plano Financeiro Proativo:** Sugerir um plano de gastos (ex: 50/30/20) baseado na renda e objetivos do usuário.
-   [ ] **Análise de Gastos:** Gerar resumos e gráficos simples sobre os gastos por categoria.
-   [ ] **Suporte a Mídia:** Permitir que o usuário envie uma foto de um recibo para registrar um gasto.
-   [ ] **Lembretes Inteligentes:** Enviar lembretes para o usuário registrar seus gastos diários ou semanais.
-   [ ] **Interface Web:** Criar um dashboard web simples para visualização dos dados.

--

## 🤝 Contribuições

Contribuições são muito bem-vindas! Se você tem ideias para novas funcionalidades, melhorias ou encontrou algum bug, sinta-se à vontade para abrir uma *Issue* ou enviar um *Pull Request*.

--
## 📷 Imagens Funcionando!

<img width="751" height="835" alt="Image" src="https://github.com/user-attachments/assets/22d4ebcc-1778-42b1-bbba-93423344ebff" />

