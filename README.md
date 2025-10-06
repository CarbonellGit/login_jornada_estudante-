# Portal do Aluno - Aplicação Web com Flask

## 1. Visão Geral

Este projeto é uma aplicação web desenvolvida em Flask que serve como um portal de login para alunos. A aplicação se integra a uma API externa (Sophia) para autenticar os usuários e, uma vez logados, os redireciona para uma página de portal.

O principal objetivo é fornecer uma interface segura e performática para o login de alunos, utilizando um sistema de cache para tokens de autenticação a fim de minimizar a latência e a carga na API externa.

## 2. Tecnologias Utilizadas

- **Backend:** Python 3 com [Flask](https://flask.palletsprojects.com/)
- **Autenticação:** Integração com a API REST Sophia
- **Segurança:**
  - [Flask-Limiter](https://flask-limiter.readthedocs.io/) para proteção contra ataques de força bruta (rate limiting).
  - Variáveis de ambiente para gerenciamento de credenciais com [python-dotenv](https://github.com/theskumar/python-dotenv).
- **Dependências:** Gerenciadas via `requirements.txt`.

## 3. Configuração do Ambiente de Desenvolvimento

Siga os passos abaixo para configurar e executar a aplicação em seu ambiente local.

### 3.1. Pré-requisitos

- Python 3.8 ou superior
- `pip` (gerenciador de pacotes do Python)
- Um editor de código de sua preferência (ex: VS Code, PyCharm)

### 3.2. Instalação

1. **Clone o repositório:**
   ```bash
   git clone <url-do-repositorio>
   cd <nome-do-diretorio>
   ```

2. **Crie e ative um ambiente virtual (recomendado):**
   ```bash
   # Para Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Para macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

### 3.3. Variáveis de Ambiente

A aplicação requer algumas variáveis de ambiente para se conectar à API Sophia e para a configuração de segurança do Flask. Crie um arquivo chamado `.env` na raiz do projeto e adicione as seguintes variáveis:

```ini
# Chave secreta para a sessão do Flask (pode ser qualquer string segura)
SECRET_KEY='sua_chave_secreta_aqui'

# Credenciais da API Sophia
SOPHIA_TENANT='seu_tenant_aqui'
SOPHIA_USER='seu_usuario_api_aqui'
SOPHIA_PASSWORD='sua_senha_api_aqui'
SOPHIA_API_HOSTNAME='hostname_da_api_sophia'
```

**Importante:** Substitua os valores de exemplo (`seu_..._aqui` e `hostname_da_api_sophia`) pelas credenciais e informações corretas fornecidas para o seu ambiente. O arquivo `.env` não deve ser enviado para o controle de versão.

## 4. Como Executar a Aplicação

Com o ambiente virtual ativado e as variáveis de ambiente configuradas, inicie o servidor de desenvolvimento do Flask com o seguinte comando:

```bash
flask run
```

Ou, alternativamente:

```bash
python app.py
```

A aplicação estará disponível em `http://127.0.0.1:5000` (ou `http://localhost:5000`) no seu navegador.

## 5. Estrutura do Projeto

```
.
├── static/              # Arquivos estáticos (CSS, JS, imagens) - (vazio por padrão)
├── templates/           # Templates HTML do Flask
│   ├── login.html       # Página de login
│   └── portal.html      # Página do portal do aluno
├── .env                 # Arquivo de variáveis de ambiente (NÃO versionado)
├── app.py               # Arquivo principal da aplicação Flask
├── requirements.txt     # Lista de dependências Python
└── README.md            # Este arquivo
```

## 6. Lógica da Aplicação

- **`app.py`**: Contém toda a lógica da aplicação, incluindo:
  - Configuração do Flask e extensões (Flask-Limiter).
  - Funções para interagir com a API Sophia (`obter_token_sistema`, `validar_login_aluno`).
  - Um cache de token em memória para otimizar a autenticação do sistema.
  - As rotas da aplicação web (`/`, `/portal`, `/logout`).
- **Templates**: As páginas são renderizadas a partir de arquivos HTML localizados na pasta `templates/`. O Flask utiliza a engine de templates Jinja2.
- **Segurança**: A rota `/portal` é protegida, e o acesso só é permitido para usuários que realizaram o login com sucesso. O login também possui um limite de tentativas para evitar ataques de força bruta.