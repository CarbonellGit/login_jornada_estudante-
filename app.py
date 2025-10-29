# """Módulo principal da aplicação de autenticação.
#
# Esta aplicação oferece duas formas de login:
# - Login de responsáveis/administradores via API Sophia (usuário e senha);
# - Login de estudantes via OAuth do Google (contas do domínio autorizado).
#
# O arquivo contém a configuração do Flask, limite de requisições, rotas
# (login, logout, portal), integração com a API Sophia para validação de
# credenciais e um cliente OAuth configurado para o Google.
#
# Observação: conforme solicitado, nenhuma lógica foi alterada — apenas
# comentários e documentação foram adicionados/ajustados em português
# brasileiro para facilitar a manutenção.
# """
#
# --- Importações ---
# Módulos padrão do Python
import os
import time
import logging

# Módulos de terceiros
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth  # <-- NOVA IMPORTAÇÃO (Etapa 2)

# --- Configuração Inicial ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Configuração do Flask e Extensões ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# --- (NOVO) Configuração do Google OAuth ---
# Inicializa o Authlib
oauth = OAuth(app)

# Carrega as credenciais do Google do arquivo .env (Etapa 1)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Registra o cliente "google".
# 'server_metadata_url' é a forma moderna de configurar o OAuth.
# Ele busca automaticamente os endpoints de autorização e token do Google.
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        # 'scope' define quais informações queremos do usuário
        'scope': 'openid email profile' # openid (obrigatório), email e profile (nome)
    }
)
# --- Fim do Bloco OAuth ---

# --- Configurações da API Sophia ---
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')

API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}"

# --- Cache Simples para o Token da API ---
token_cache = {
    "token": None,
    "expires_at": 0
}
TOKEN_LIFESPAN_SECONDS = 1800

# --- Funções de Lógica da API (Sem alterações) ---

def obter_token_sistema():
    """
    Obtém o token de autenticação do sistema da API Sophia, utilizando um cache
    para evitar requisições desnecessárias. (Sem alterações)
    """
    if token_cache["token"] and time.time() < token_cache["expires_at"]:
        logging.info("Token do sistema (Sophia) obtido do cache.")
        return token_cache["token"]

    logging.info("Cache de token (Sophia) expirado. Solicitando novo token.")
    
    auth_url = f"{API_BASE_URL}/api/v1/Autenticacao"
    auth_data = {"usuario": SOPHIA_USER, "senha": SOPHIA_PASSWORD}

    try:
        response = requests.post(auth_url, json=auth_data, timeout=15)
        response.raise_for_status()
        novo_token = response.text.strip() if response.text else None
        
        if novo_token:
            token_cache["token"] = novo_token
            token_cache["expires_at"] = time.time() + TOKEN_LIFESPAN_SECONDS
            logging.info("Novo token do sistema (Sophia) obtido com sucesso.")
            return novo_token
        else:
            logging.warning("API de autenticação (Sophia) retornou resposta vazia.")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao obter token do sistema (Sophia): {e}")
        return None

def validar_login_aluno(token, codigo, senha):
    """
    Valida as credenciais de login de um aluno/responsável (código/RM e senha)
    junto à API Sophia. (Sem alterações)
    """
    validation_url = f"{API_BASE_URL}/api/v1/Alunos/ValidarLogin"
    payload = {"codigo": codigo, "senha": senha}
    headers = {'token': token, 'Content-Type': 'application/json'}

    try:
        response = requests.post(validation_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error("Falha ao decodificar JSON da API de validação (Sophia).")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao validar login (Sophia): {e}")
        return None

# --- Rotas da Aplicação Web ---

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """
    Renderiza a página de login e processa a tentativa de login do RESPONSÁVEL (API Sophia).
    O login de estudante é tratado por rotas separadas (/login/google).
    """
    
    # Se o usuário já está logado, vai para o portal
    if 'usuario_logado' in session:
        return redirect(url_for('portal'))

    # Se a requisição for POST, é um login de RESPONSÁVEL
    if request.method == 'POST':
        
        # --- Lógica POST (Login Responsável - API Sophia) ---
        
        # 1. Obter dados do formulário
        codigo_usuario = request.form.get('codigo')
        senha_usuario = request.form.get('senha')

        # 2. Validação básica de entrada
        if not codigo_usuario or not senha_usuario:
            flash('Código e senha são obrigatórios!')
            return render_template('login.html')

        # 3. Obter o Token do Sistema
        token_sistema = obter_token_sistema()
        if not token_sistema:
            flash('Erro crítico no sistema. Tente novamente mais tarde.')
            return render_template('login.html')

        # 4. Validar as Credenciais do Aluno/Responsável na API Sophia
        resposta_validacao = validar_login_aluno(token_sistema, codigo_usuario, senha_usuario)

        # 5. Processar a Resposta da Validação
        if resposta_validacao and resposta_validacao.get('acessoValido'):
            # --- Login bem-sucedido (Responsável) ---
            session['usuario_logado'] = True
            session['aluno_id'] = resposta_validacao.get('alunoId', codigo_usuario)
            # (Pequena melhoria: definimos o nome padrão como 'Responsável' neste fluxo)
            session['aluno_nome'] = resposta_validacao.get('nome', 'Responsável') 
            
            logging.info(f"Login (Responsável) bem-sucedido para o usuário com código: {codigo_usuario}")
            
            return redirect(url_for('portal'))
        else:
            # --- Login falho (Responsável) ---
            logging.warning(f"Tentativa de login (Responsável) falha para o usuário com código: {codigo_usuario}")
            flash('Código ou senha inválidos.')
            return render_template('login.html')

    # Se for GET, apenas mostra a página de login
    return render_template('login.html')

# --- (NOVAS) ROTAS PARA LOGIN GOOGLE ---

@app.route('/login/google')
def login_google():
    """
    Rota para iniciar o fluxo de login do Google.
    Esta função é chamada quando o usuário clica em "Entrar com Google".
    (O nome 'login_google' corresponde ao url_for() no login.html)
    """
    # Define a URL para onde o Google deve redirecionar após o login
    # 'auth_callback' é o nome da *próxima* função
    # _external=True é necessário para o OAuth
    redirect_uri = url_for('auth_callback', _external=True)
    
    # Usa o cliente 'google' (que registramos) para criar a URL de autorização
    # e redireciona o usuário para ela.
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def auth_callback():
    """
    Rota de retorno (callback) — o Google redireciona o usuário para aqui após o
    processo de autenticação. Nesta rota validamos os dados recebidos e criamos
    a sessão do usuário.

    Observação: esta URL deve corresponder à URL configurada nas credenciais do
    Google (Etapa de configuração do OAuth).
    """
    try:
    # 1. Obtém o token de acesso enviado pelo Google
    #    (este token já pode conter as informações do usuário - 'userinfo'
    #    conforme a configuração de escopos)
        token = oauth.google.authorize_access_token()
        
        # 2. (CORRIGIDO) Extrai as informações do usuário ('userinfo') do objeto
        #    token (evita uma chamada adicional à API de userinfo que vinha
        #    falhando em alguns cenários).
        user_info = token.get('userinfo')

        # 2.1 (MELHORIA) Verifica se as informações do usuário realmente foram
        # obtidas no token antes de prosseguir.
        if not user_info:
            logging.error("Falha ao obter as informações do usuário ('userinfo') no token do Google.")
            flash('Ocorreu um erro ao ler os dados do Google. Tente novamente.')
            return redirect(url_for('login'))

        # 3. --- PONTO CRÍTICO: Validação do Domínio ---
        user_email = user_info.get('email', '')
        
        # !! IMPORTANTE !!
        # Confirme se este é o domínio exato.
        DOMINIO_PERMITIDO = '@soucarbonell.com.br' 

    # .lower() torna a verificação insensível a maiúsculas/minúsculas (mais seguro)
        if user_email and user_email.lower().endswith(DOMINIO_PERMITIDO):
            # --- Login bem-sucedido (Estudante) ---
            
            # 4. Cria a sessão do usuário (similar ao login de responsável)
            session['usuario_logado'] = True
            session['aluno_id'] = user_email # Usamos o email como ID para estudantes
            session['aluno_nome'] = user_info.get('name', 'Estudante') # Pega o nome do perfil
            
            logging.info(f"Login (Estudante Google) bem-sucedido para: {user_email}")
            
            # 5. Redireciona para o portal
            return redirect(url_for('portal'))
        else:
            # --- Falha: Domínio não permitido ---
            logging.warning(f"Tentativa de login (Estudante Google) falha. E-mail não permitido: {user_email}")
            flash(f"Acesso negado. Apenas contas do domínio {DOMINIO_PERMITIDO} são permitidas.")
            return redirect(url_for('login'))

    except Exception as e:
        # --- Falha: Erro genérico no OAuth ---
        # (Ex: usuário nega permissão, token expira, etc.)
        logging.error(f"Erro durante o callback do Google OAuth: {e}")
        flash('Ocorreu um erro durante a autenticação com o Google. Tente novamente.')
        return redirect(url_for('login'))
    
# --- ROTA PORTAL (Sem alteração) ---
@app.route('/portal')
def portal():
    """
    Renderiza a página principal do portal, que é protegida
    e acessível apenas para usuários logados. (Sem alterações)
    """
    if 'usuario_logado' not in session:
        flash('Você precisa fazer login para acessar esta página.')
        return redirect(url_for('login'))
    
    return render_template('portal.html', nome_aluno=session.get('aluno_nome'))

# --- ROTA LOGOUT (Sem alteração) ---
@app.route('/logout')
def logout():
    """
    Processa o logout do usuário, limpando a sessão. (Sem alterações)
    """
    usuario_id = session.get('aluno_id', 'desconhecido')
    
    session.clear()
    
    flash('Você foi desconectado com sucesso.')
    logging.info(f"Usuário {usuario_id} desconectado.")
    
    return redirect(url_for('login'))

# --- Bloco de Execução (Sem alteração) ---
if __name__ == '__main__':
    # host='0.0.0.0' é importante para rodar localmente de forma acessível
    # O SSL (https) é necessário para o OAuth em produção,
    # mas 'http://127.0.0.1:5000' é permitido para testes locais.
    app.run(host='0.0.0.0', port=5000)
