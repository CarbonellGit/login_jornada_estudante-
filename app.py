# app.py

# --- Importações ---
# Módulos padrão do Python (já vêm com o Python)
import os  # Para acessar variáveis de ambiente (ex: SECRET_KEY, dados da API)
import time  # Para verificar o tempo de expiração do token (usando time.time())
import logging  # Para registrar eventos, erros e informações de depuração

# Módulos de terceiros (necessário instalar: pip install Flask python-dotenv requests Flask-Limiter)
import requests  # Para fazer chamadas HTTP (requisições) para a API Sophia
from dotenv import load_dotenv  # Para carregar variáveis de ambiente do arquivo .env
from flask import Flask, render_template, request, redirect, url_for, session, flash
# Flask: O micro-framework principal que roda a aplicação web
# render_template: Para carregar arquivos HTML (que devem estar na pasta 'templates')
# request: Para acessar dados enviados pelo usuário (ex: request.form['codigo'])
# redirect: Para redirecionar o usuário para outra URL
# url_for: Para construir URLs dinamicamente (ex: url_for('login'))
# session: Um "dicionário" seguro que armazena dados do usuário entre requisições (ex: session['usuario_logado'])
# flash: Para exibir mensagens rápidas para o usuário (ex: "Login inválido")
from flask_limiter import Limiter  # Importa a classe principal do Flask-Limiter
from flask_limiter.util import get_remote_address  # Função para identificar o usuário pelo seu endereço de IP

# --- Configuração Inicial ---
# Carrega as variáveis de ambiente do arquivo .env para o sistema operacional
# Isso permite que os.getenv() encontre chaves definidas no .env (como 'SECRET_KEY')
load_dotenv()

# Configura o sistema de logging para registrar informações importantes e erros.
# Isso é crucial para monitorar a aplicação em produção.
logging.basicConfig(
    level=logging.INFO,  # Define o nível mínimo de log (INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s'  # Define o formato da mensagem de log
)

# --- Configuração do Flask e Extensões ---
# Inicializa a aplicação Flask. '__name__' é uma variável especial do Python
# que ajuda o Flask a encontrar recursos como templates.
app = Flask(__name__)

# Define a 'SECRET_KEY' (chave secreta) para a aplicação.
# É crucial para proteger as sessões do usuário e dados de cookies contra manipulação.
# O valor é pego das variáveis de ambiente (do arquivo .env).
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Configura o Flask-Limiter para proteger a aplicação contra ataques de força bruta.
limiter = Limiter(
    # Usa o endereço de IP do cliente (get_remote_address) como identificador
    # para contar as requisições.
    get_remote_address,
    app=app,  # Associa o limiter à nossa aplicação Flask ('app')
    default_limits=["200 per day", "50 per hour"]  # Limites padrão para *todas* as rotas
)

# --- Configurações da API Sophia ---
# Pega as credenciais e endereços da API a partir das variáveis de ambiente (.env)
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')

# Monta a URL base para todas as chamadas da API, usando f-strings para inserir as variáveis.
API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}"

# --- Cache Simples para o Token da API ---
# Design Pattern: Cache em memória para evitar requisições repetidas.
# Objetivo: Armazenar o token do sistema para reutilização, melhorando a performance
# e reduzindo a carga na API externa.
# Este é um dicionário Python simples que atua como nosso cache.
token_cache = {
    "token": None,  # Armazena o token de acesso da API
    "expires_at": 0  # Armazena o timestamp UNIX de quando o token expira
}
# O token da API Sophia expira em 30 minutos (1800 segundos).
# Usamos esta constante para calcular o 'expires_at'.
TOKEN_LIFESPAN_SECONDS = 1800

# --- Funções de Lógica da API ---

def obter_token_sistema():
    """
    Obtém o token de autenticação do sistema da API Sophia, utilizando um cache
    para evitar requisições desnecessárias.

    A função primeiro verifica o cache. Se o token existir e ainda for válido,
    retorna-o imediatamente. Caso contrário, faz uma nova requisição à API.

    Returns:
        str: O token de autenticação, se obtido com sucesso.
        None: Se ocorrer um erro na comunicação com a API ou a resposta for inválida.
    """
    # 1. Verifica se o token em cache ainda é válido
    # Compara o tempo atual (time.time()) com o tempo de expiração guardado.
    if token_cache["token"] and time.time() < token_cache["expires_at"]:
        # Se o token existe E o tempo atual é MENOR que o de expiração, o token é válido.
        logging.info("Token do sistema obtido do cache.")
        return token_cache["token"]

    # 2. Se o cache estiver expirado ou vazio, solicita um novo token à API
    logging.info("Cache de token expirado ou vazio. Solicitando novo token do sistema.")
    
    # Define o endpoint (URL específica) para autenticação do sistema
    auth_url = f"{API_BASE_URL}/api/v1/Autenticacao"
    # Prepara os dados de autenticação (usuário e senha do *sistema*)
    auth_data = {"usuario": SOPHIA_USER, "senha": SOPHIA_PASSWORD}

    try:
        # 3. Realiza a requisição POST para a API de autenticação
        # 'json=auth_data' envia os dados no formato JSON
        # 'timeout=15' define um limite de 15 segundos para a resposta.
        response = requests.post(auth_url, json=auth_data, timeout=15)
        
        # 4. Lança uma exceção (erro) para códigos de status 4xx (erro do cliente)
        # ou 5xx (erro do servidor). Isso é uma boa prática para capturar erros da API.
        response.raise_for_status()

        # 5. Processa a resposta
        # Pega o texto da resposta (o token) e remove espaços em branco (ex: \n) com .strip()
        novo_token = response.text.strip() if response.text else None
        
        if novo_token:
            # 6. Armazena o novo token e calcula seu tempo de expiração
            token_cache["token"] = novo_token
            token_cache["expires_at"] = time.time() + TOKEN_LIFESPAN_SECONDS
            
            logging.info("Novo token do sistema obtido e cache atualizado com sucesso.")
            return novo_token
        else:
            # Se a API respondeu com 200 OK, mas o corpo estava vazio
            logging.warning("API de autenticação retornou uma resposta vazia.")
            return None

    # 7. Captura exceções específicas de rede (timeout, erro de DNS, conexão recusada, etc.)
    except requests.exceptions.RequestException as e:
        # Loga o erro detalhado para facilitar a depuração
        logging.error(f"Falha ao obter token do sistema da API Sophia: {e}")
        return None

def validar_login_aluno(token, codigo, senha):
    """
    Valida as credenciais de login de um aluno (código/RM e senha)
    junto à API Sophia.

    Args:
        token (str): O token de autenticação do *sistema* (obtido de obter_token_sistema).
        codigo (str): O código (RM) do aluno.
        senha (str): A senha do aluno.

    Returns:
        dict: A resposta da API em formato JSON se a validação for bem-sucedida.
              Ex: {"acessoValido": true, "alunoId": 123, "nome": "..."}
        None: Se ocorrer um erro de comunicação ou a resposta for inválida (ex: não-JSON).
    """
    # Define o endpoint específico para validar o login do aluno
    validation_url = f"{API_BASE_URL}/api/v1/Alunos/ValidarLogin"
    # Define os dados (payload) que serão enviados no corpo da requisição
    payload = {"codigo": codigo, "senha": senha}
    # Define os cabeçalhos (headers) da requisição, incluindo o token do sistema
    # O 'Content-Type' informa à API que estamos enviando JSON.
    headers = {'token': token, 'Content-Type': 'application/json'}

    try:
        # 1. Realiza a requisição POST para a API de validação
        response = requests.post(validation_url, headers=headers, json=payload, timeout=30)
        # 2. Garante o tratamento de erros HTTP (4xx, 5xx)
        response.raise_for_status()
        
        # 3. Tenta decodificar a resposta JSON.
        # Se a API retornar um JSON válido, .json() o converte para um dicionário Python.
        return response.json()

    # 4. Tratamento de Erros Específicos
    except requests.exceptions.JSONDecodeError:
        # Ocorre se a API responder com 200 OK, mas o corpo não for um JSON válido
        logging.error("Falha ao decodificar a resposta JSON da API de validação de login.")
        return None
    except requests.exceptions.RequestException as e:
        # Ocorre por falhas de rede, timeouts, ou erros 4xx/5xx (capturados por raise_for_status)
        logging.error(f"Falha ao validar login do aluno na API Sophia: {e}")
        return None

# --- Rotas da Aplicação Web ---

# @app.route define uma rota (URL) para a aplicação.
# '/' é a rota raiz (página inicial).
# methods=['GET', 'POST'] permite que esta rota aceite tanto requisições GET (carregar a página)
# quanto POST (enviar o formulário de login).
@app.route('/', methods=['GET', 'POST'])
# @limiter.limit aplica um limite de taxa específico para esta rota (Login).
# "10 per minute" (10 por minuto) por IP, protegendo contra força bruta.
@limiter.limit("10 per minute")
def login():
    """
    Renderiza a página de login (requisição GET) e 
    processa a tentativa de login do usuário (requisição POST).
    """
    
    # --- Lógica GET (ou se o usuário já está logado) ---
    
    # Se o usuário já tem 'usuario_logado' na sua sessão (cookie seguro),
    # ele já está autenticado, então redirecionamos para o portal.
    if 'usuario_logado' in session:
        return redirect(url_for('portal')) # 'portal' é o nome da função portal() abaixo

    # Se a requisição for POST, significa que o usuário enviou o formulário de login
    if request.method == 'POST':
        
        # --- Lógica POST (Processamento do Formulário) ---
        
        # 1. Obter dados do formulário enviado (dos campos 'name' do HTML)
        codigo_usuario = request.form.get('codigo')
        senha_usuario = request.form.get('senha')

        # 2. Validação básica de entrada (campos não podem estar vazios)
        if not codigo_usuario or not senha_usuario:
            flash('Código e senha são obrigatórios!')
            return render_template('login.html')

        # 3. Obter o Token do Sistema (usando nossa função com cache)
        token_sistema = obter_token_sistema()
        if not token_sistema:
            # Se o token do sistema falhar (API offline, etc.), é um erro crítico.
            # Mensagem genérica para o usuário. O erro real está no log (logging.error).
            flash('Erro crítico no sistema. Tente novamente mais tarde.')
            return render_template('login.html')

        # 4. Validar as Credenciais do Aluno na API Sophia
        resposta_validacao = validar_login_aluno(token_sistema, codigo_usuario, senha_usuario)

        # 5. Processar a Resposta da Validação
        
        # Verifica se a 'resposta_validacao' não é None E se a chave 'acessoValido' é True
        if resposta_validacao and resposta_validacao.get('acessoValido'):
            # --- Login bem-sucedido ---
            
            # Armazena na sessão (cookie seguro) que o usuário está logado
            session['usuario_logado'] = True
            
            # Armazena outras informações úteis da API na sessão para uso futuro
            # .get() é usado para evitar erros caso a chave não exista (retorna o valor padrão)
            session['aluno_id'] = resposta_validacao.get('alunoId', codigo_usuario)
            session['aluno_nome'] = resposta_validacao.get('nome', 'Estudante')
            
            logging.info(f"Login bem-sucedido para o usuário com código: {codigo_usuario}")
            
            # Redireciona o usuário para a rota 'portal'
            return redirect(url_for('portal'))
        else:
            # --- Login falho (Credenciais inválidas ou erro na API) ---
            
            # Loga a tentativa de login falha para monitoramento de segurança
            logging.warning(f"Tentativa de login falha para o usuário com código: {codigo_usuario}")
            flash('Código ou senha inválidos.')
            return render_template('login.html')

    # Se a requisição for GET (o usuário apenas abriu a página),
    # mostra o template 'login.html'.
    return render_template('login.html')

@app.route('/portal')
def portal():
    """
    Renderiza a página principal do portal, que é protegida
    e acessível apenas para usuários logados.
    """
    
    # 1. Proteção da Rota: Verifica se a chave 'usuario_logado' NÃO está na sessão.
    if 'usuario_logado' not in session:
        # Se não estiver, o usuário não está logado.
        flash('Você precisa fazer login para acessar esta página.')
        # Redireciona-o de volta para a página de login.
        return redirect(url_for('login'))
    
    # 2. Renderização da Página
    # Se o usuário está logado, busca o nome na sessão (que salvamos durante o login)
    # e o envia para o template 'portal.html' (para exibir "Bem-vindo, [Nome]").
    return render_template('portal.html', nome_aluno=session.get('aluno_nome'))

@app.route('/logout')
def logout():
    """
    Processa o logout do usuário, limpando a sessão.
    """
    # Pega o ID do aluno da sessão *antes* de limpá-la, apenas para o log.
    usuario_id = session.get('aluno_id', 'desconhecido')
    
    # session.clear() remove TODOS os dados armazenados na sessão do usuário
    # (ex: 'usuario_logado', 'aluno_id', 'aluno_nome').
    session.clear()
    
    flash('Você foi desconectado com sucesso.')
    logging.info(f"Usuário {usuario_id} desconectado.")
    
    # Redireciona o usuário para a página de login
    return redirect(url_for('login'))

# --- Bloco de Execução ---

# O bloco `if __name__ == '__main__':` é uma convenção do Python.
# Ele significa: "Execute o código abaixo apenas se este script
# for rodado diretamente (ex: 'python app.py')".
# Isso evita que o servidor rode se o arquivo for *importado* por outro script.
if __name__ == '__main__':
    # Em um ambiente de produção real, um servidor WSGI (Web Server Gateway Interface)
    # como Gunicorn ou uWSGI deve ser usado no lugar de app.run().
    # Ex (no terminal): gunicorn -w 4 "app:app"
    
    # O modo debug NUNCA deve ser ativado em produção (debug=True),
    # pois expõe falhas de segurança.
    # host='0.0.0.0' faz o servidor ser acessível por qualquer IP na rede local.
    app.run(host='0.0.0.0', port=5000)
