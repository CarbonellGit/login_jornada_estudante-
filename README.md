# Portal do @soucarbonell - Aplicação Web com Flask

## 1. Visão Geral

Este projeto é uma aplicação web desenvolvida em Flask que serve como um portal de login para alunos e responsáveis/administradores. A aplicação suporta duas formas de autenticação:

- Login de responsáveis/administradores via API Sophia (usuário e senha).
- Login de estudantes via Google OAuth (apenas contas do domínio permitido).

A aplicação utiliza um cache simples em memória para o token do sistema (Sophia) para reduzir chamadas desnecessárias à API e melhorar latência.

## 2. O que foi alterado / por que este README foi atualizado

Nas últimas alterações foi adicionado suporte a login via Google (OAuth2/OpenID Connect) usando Authlib. Principais mudanças:

- Inclusão de um cliente OAuth do Google e duas novas rotas:
  - `/login/google` para iniciar o fluxo OAuth.
  - `/login/google/callback` para processar o retorno do Google.
- Extração de informações do usuário diretamente do token retornado (campo `userinfo`), evitando chamadas adicionais.
- Verificação do domínio do e-mail do usuário para permitir apenas contas do domínio autorizado (`@soucarbonell.com.br` por padrão — isso está atualmente definido no código e pode ser alterado conforme necessário).
- O fluxo de login via Sophia (API) e o cache de token continuam presentes.
- Foi adicionado tratamento de erros e logs mais claros para o fluxo OAuth.

## 3. Tecnologias Utilizadas

- Backend: Python 3 com Flask
- Autenticação:
  - Integração com a API REST Sophia (login via código/RM + senha)
  - Google OAuth (Authlib)
- Segurança:
  - Flask-Limiter para proteção contra ataques de força bruta (rate limiting)
  - Variáveis de ambiente gerenciadas com python-dotenv
- Requisições HTTP: requests
- Dependências: gerenciadas via `requirements.txt`

Observação: para suporte ao Google OAuth, a biblioteca `authlib` foi adicionada às dependências.

## 4. Pré-requisitos

- Python 3.8 ou superior
- pip
- Conta Google com credenciais de OAuth (Client ID e Client Secret) configuradas para permitir o redirect URI da aplicação
- Acesso às credenciais/tenant da API Sophia

## 5. Instalação

1. Clone o repositório:
   ```bash
   git clone <url-do-repositorio>
   cd login-jornada-estudante
   ```

2. Crie e ative um ambiente virtual (recomendado):
   ```bash
   # Para Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Para macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## 6. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as variáveis abaixo. Substitua os valores de exemplo pelos valores reais:

```ini
# Chave secreta para a sessão do Flask
SECRET_KEY='sua_chave_secreta_aqui'

# Credenciais da API Sophia
SOPHIA_TENANT='seu_tenant_aqui'
SOPHIA_USER='seu_usuario_api_aqui'
SOPHIA_PASSWORD='sua_senha_api_aqui'
SOPHIA_API_HOSTNAME='hostname_da_api_sophia'  # ex: api.exemplo.com

# Credenciais do Google (para OAuth/OpenID Connect)
GOOGLE_CLIENT_ID='seu_google_client_id_aqui'
GOOGLE_CLIENT_SECRET='seu_google_client_secret_aqui'
```

Importante:
- O código atualmente verifica o domínio permitido com uma constante definida em `app.py`:
  - DOMINIO_PERMITIDO = '@soucarbonell.com.br'
  - Se desejar alterar o domínio sem mexer no código, você pode adaptar `app.py` para ler um valor de `.env`.
- O arquivo `.env` não deve ser versionado (adicione ao .gitignore).

## 7. Configuração do Google OAuth

1. No Console de APIs do Google, crie um novo par de credenciais OAuth (Client ID).
2. Configure o redirect URI para apontar para:
   - Em desenvolvimento: `http://127.0.0.1:5000/login/google/callback`
   - Em produção: a URL HTTPS correspondente.
3. Preencha `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no `.env`.

Observação: O `server_metadata_url` usado no cliente OAuth busca automaticamente os endpoints de autorização e token do Google.

## 8. Como Executar a Aplicação

Com o ambiente virtual ativado e o `.env` configurado, inicie o servidor:

```bash
flask run
```

ou

```bash
python app.py
```

A aplicação ficará disponível em `http://127.0.0.1:5000`. Para testes locais do OAuth, http é permitido para `localhost`, mas em produção você deve usar HTTPS.

## 9. Fluxos de Login

- Responsável / Administrador (via Sophia API)
  - A rota principal `/` (formulário de login) aceita POST com `codigo` e `senha`.
  - O backend solicita um token do sistema (cacheado em memória) e chama o endpoint de validação da Sophia.
  - Em caso de sucesso, a sessão é criada com `usuario_logado`, `aluno_id` e `aluno_nome`.

- Estudante (via Google OAuth)
  - Clique em "Entrar com Google" (botão que deve existir em `templates/login.html`) para iniciar `GET /login/google`.
  - Após autenticação no Google, o callback `/login/google/callback` processa o token e extrai `userinfo`.
  - É feito o controle de domínio do e-mail (atualmente `@soucarbonell.com.br`). Se permitido, a sessão é criada como no fluxo da Sophia.

## 10. Segurança e Limites

- As rotas são protegidas por limites de requisições com Flask-Limiter (`default_limits` e limites específicos em rotas sensíveis).
- Use variáveis de ambiente para segredos e credenciais.
- Em produção, ative HTTPS/SSL — OAuth em produção normalmente requer HTTPS.

## 11. Estrutura do Projeto

```
.
├── static/              # Arquivos estáticos (CSS, JS, imagens)
├── templates/           # Templates HTML do Flask
│   ├── login.html       # Página de login (deve incluir botão "Entrar com Google")
│   └── portal.html      # Página do portal do aluno
├── .env                 # Arquivo de variáveis de ambiente (NÃO versionado)
├── app.py               # Arquivo principal da aplicação Flask
├── requirements.txt     # Lista de dependências Python (inclui authlib, requests, python-dotenv, flask-limiter)
└── README.md            # Este arquivo
```

## 12. Observações Técnicas Relevantes

- Token da Sophia:
  - Existe um cache simples em memória (`token_cache`) com tempo de vida padrão (ex.: 1800s) para reduzir chamadas à API de autenticação.
  - Se o token expirar ou não for obtido, a autenticação via Sophia falhará até que o token seja renovado.

- Google OAuth:
  - O aplicativo usa `authlib.integrations.flask_client.OAuth`.
  - Informações do usuário são extraídas do `token.get('userinfo')`. Se `userinfo` não estiver presente, ocorre erro e o usuário é redirecionado ao login.

- Logs:
  - A aplicação registra informações de fluxo (sucesso/falha de logins, erros de integração) para facilitar diagnóstico.

- Desenvolvido by: Thiago Marques


