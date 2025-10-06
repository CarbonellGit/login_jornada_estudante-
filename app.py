# app.py

# --- Importações ---
# Módulos padrão do Python
import os
import time
import logging

# Módulos de terceiros (necessário instalar: pip install Flask python-dotenv requests Flask-Limiter)
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Configuração Inicial ---
# Carrega as variáveis de ambiente do arquivo .env para o sistema operacional
load_dotenv()

# Configura o sistema de logging para registrar informações importantes e erros.
# Isso é crucial para monitorar a aplicação em produção.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Configuração do Flask e Extensões ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Configura o Flask-Limiter para proteger a aplicação contra ataques de força bruta.
# Ele usa o endereço de IP do cliente como identificador para limitar as requisições.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"] # Limites padrão para todas as rotas
)

# --- Configurações da API Sophia ---
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')
API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}"

# --- Cache Simples para o Token da API ---
# Design Pattern: Cache em memória para evitar requisições repetidas.
# Objetivo: Armazenar o token do sistema para reutilização, melhorando a performance
# e reduzindo a carga na API externa.
token_cache = {
    "token": None,
    "expires_at": 0  # Timestamp de quando o token expira
}
# O token da API Sophia expira em 30 minutos (1800 segundos).
TOKEN_LIFESPAN_SECONDS = 1800

# --- Funções de Lógica da API ---

def obter_token_sistema():
    """
    Obtém o token de autenticação do sistema da API Sophia, utilizando um cache
    para evitar requisições desnecessárias.

    Returns:
        str: O token de autenticação, se obtido com sucesso.
        None: Se ocorrer um erro na comunicação com a API.
    """
    # 1. Verifica se o token em cache ainda é válido
    if token_cache["token"] and time.time() < token_cache["expires_at"]:
        logging.info("Token do sistema obtido do cache.")
        return token_cache["token"]

    # 2. Se o cache estiver expirado ou vazio, solicita um novo token à API
    logging.info("Cache de token expirado ou vazio. Solicitando novo token do sistema.")
    auth_url = f"{API_BASE_URL}/api/v1/Autenticacao"
    auth_data = {"usuario": SOPHIA_USER, "senha": SOPHIA_PASSWORD}

    try:
        # Realiza a requisição POST para a API de autenticação
        response = requests.post(auth_url, json=auth_data, timeout=15)
        # Lança uma exceção HTTPError para códigos de status 4xx ou 5xx.
        # Isso garante que erros da API sejam capturados e registrados.
        response.raise_for_status()

        novo_token = response.text.strip() if response.text else None
        if novo_token:
            # Armazena o novo token e calcula seu tempo de expiração
            token_cache["token"] = novo_token
            token_cache["expires_at"] = time.time() + TOKEN_LIFESPAN_SECONDS
            logging.info("Novo token do sistema obtido e cache atualizado com sucesso.")
            return novo_token
        else:
            logging.warning("API de autenticação retornou uma resposta vazia.")
            return None

    # Captura exceções específicas de rede (timeout, erro de DNS, etc.)
    except requests.exceptions.RequestException as e:
        # Loga o erro detalhado para facilitar a depuração
        logging.error(f"Falha ao obter token do sistema da API Sophia: {e}")
        return None

def validar_login_aluno(token, codigo, senha):
    """
    Valida as credenciais de login de um aluno junto à API Sophia.

    Args:
        token (str): O token de autenticação do sistema.
        codigo (str): O código (RM) do aluno.
        senha (str): A senha do aluno.

    Returns:
        dict: A resposta da API em formato JSON se a validação for bem-sucedida.
        None: Se ocorrer um erro de comunicação ou a resposta for inválida.
    """
    validation_url = f"{API_BASE_URL}/api/v1/Alunos/ValidarLogin"
    payload = {"codigo": codigo, "senha": senha}
    headers = {'token': token, 'Content-Type': 'application/json'}

    try:
        response = requests.post(validation_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # Garante o tratamento de erros HTTP
        
        # Tenta decodificar a resposta JSON. Se falhar, captura a exceção.
        return response.json()

    except requests.exceptions.JSONDecodeError:
        logging.error("Falha ao decodificar a resposta JSON da API de validação de login.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao validar login do aluno na API Sophia: {e}")
        return None

# --- Rotas da Aplicação Web ---

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # Aplica o limite de 10 tentativas por minuto por IP
def login():
    # Se o usuário já está logado, redireciona para o portal
    if 'usuario_logado' in session:
        return redirect(url_for('portal'))

    if request.method == 'POST':
        codigo_usuario = request.form.get('codigo')
        senha_usuario = request.form.get('senha')

        if not codigo_usuario or not senha_usuario:
            flash('Código e senha são obrigatórios!')
            return render_template('login.html')

        # Utiliza a função com cache para obter o token
        token_sistema = obter_token_sistema()
        if not token_sistema:
            # Mensagem genérica para o usuário, mas o erro detalhado está no log
            flash('Erro crítico no sistema. Tente novamente mais tarde.')
            return render_template('login.html')

        resposta_validacao = validar_login_aluno(token_sistema, codigo_usuario, senha_usuario)

        # Verifica se a resposta da API é válida e se o acesso foi permitido
        if resposta_validacao and resposta_validacao.get('acessoValido'):
            # Armazena mais informações na sessão para uso futuro
            session['usuario_logado'] = True
            # Assumindo que a API retorna esses campos. Ajustar conforme a resposta real.
            session['aluno_id'] = resposta_validacao.get('alunoId', codigo_usuario)
            session['aluno_nome'] = resposta_validacao.get('nome', 'Estudante')
            
            logging.info(f"Login bem-sucedido para o usuário com código: {codigo_usuario}")
            return redirect(url_for('portal'))
        else:
            # Loga a tentativa de login falha para monitoramento de segurança
            logging.warning(f"Tentativa de login falha para o usuário com código: {codigo_usuario}")
            flash('Código ou senha inválidos.')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/portal')
def portal():
    # Protege a rota, garantindo que apenas usuários autenticados possam acessá-la
    if 'usuario_logado' not in session:
        flash('Você precisa fazer login para acessar esta página.')
        return redirect(url_for('login'))
    
    # Passa as informações do usuário da sessão para o template
    return render_template('portal.html', nome_aluno=session.get('aluno_nome'))

@app.route('/logout')
def logout():
    # Limpa todos os dados da sessão
    usuario_id = session.get('aluno_id', 'desconhecido')
    session.clear()
    flash('Você foi desconectado com sucesso.')
    logging.info(f"Usuário {usuario_id} desconectado.")
    return redirect(url_for('login'))

# --- Bloco de Execução ---
if __name__ == '__main__':
    # Em um ambiente de produção, um servidor WSGI como Gunicorn ou uWSGI deve ser usado.
    # O modo debug NUNCA deve ser ativado em produção.
    # A variável de ambiente FLASK_DEBUG pode ser usada para controlar isso dinamicamente.
    # Ex: export FLASK_DEBUG=true (para desenvolvimento)
    app.run(host='0.0.0.0', port=5000)