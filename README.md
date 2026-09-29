# Cofrinho AO — API (Django)

Backend do Cofrinho AO: contas, login por dispositivo, verificação de email (Brevo), recuperação de senha e sincronização de dados (transacções, categorias, metas).

Stack: Django 5 · Django REST Framework · PostgreSQL (Neon) em produção, SQLite em desenvolvimento · Render.

## 1. Correr no PC (PowerShell)

```powershell
cd .\cofrinho-ao-api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

(Usar `.\.venv\Scripts\python.exe` directamente evita o problema da política de scripts do PowerShell. Se preferires activar o ambiente: `.\.venv\Scripts\Activate.ps1`.)

- Verificação rápida: `http://localhost:8000/api/saude/` deve devolver `{"estado": "ok"}`.
- Sem `BREVO_API_KEY`, o código de verificação aparece **na consola** e no campo `codigoDev` da resposta (só com `DEBUG=True`).
- Painel de administração: `python manage.py createsuperuser` e abre `/admin/`.
- Testes: `.\.venv\Scripts\python.exe manage.py test` (18 testes).

## 2. Endpoints

Todos sob `/api/`. Erros: `{"erro": "mensagem", "codigo": "...", "campos": {...}}`. Chaves em camelCase (iguais às da app).

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| POST | `auth/registar/` | `nomeCompleto, username, telefone, email, senha` | 201 `{email, emailEnviado, codigoDev?}` |
| POST | `auth/reenviar-codigo/` | `email` | 200 |
| POST | `auth/verificar-email/` | `email, codigo, dispositivo?` | `{token, perfil}` |
| POST | `auth/login/` | `identificador, senha, dispositivo?` | `{token, perfil}` (403 `email_nao_verificado`) |
| POST | `auth/logout/` | — | 204 (só este dispositivo) |
| GET/PATCH | `auth/eu/` | `nomeCompleto?, username?, telefone?` | perfil |
| POST | `auth/senha/pedir/` | `email` | 200 (igual exista ou não a conta) |
| POST | `auth/senha/confirmar/` | `email, codigo, novaSenha` | 200; termina todas as sessões |
| POST | `sync/` | ver abaixo | alterações do servidor |

Autenticação: cabeçalho `Authorization: Bearer <token>`. A sessão expira após 90 dias sem uso. Só o hash do token fica na base de dados.

### Sincronização (`POST /api/sync/`)

```json
{
  "desde": "<servidorAgora recebido da última vez, ou null>",
  "categorias": [{"id": "uuid", "nome": "...", "tipo": "gasto", "escopo": "ambos", "padrao": true, "atualizadoEm": "ISO", "apagado": false}],
  "transacoes": [{"id": "uuid", "tipo": "gasto", "valor": 1500, "data": "ISO", "descricao": "", "categoria": "Alimentação", "modo": "pessoal", "atualizadoEm": "ISO", "apagado": false}],
  "metas": [{"id": "uuid", "nome": "...", "valorAlvo": 90000, "valorAtual": 0, "dataAlvo": null, "atualizadoEm": "ISO", "apagado": false}]
}
```

A resposta traz `categorias`, `transacoes`, `metas` (o que mudou no servidor desde `desde`), `servidorAgora` (guardar para o pedido seguinte) e `rejeitados` (registos inválidos, com o motivo).

Regras:
- **Conflitos:** ganha o `atualizadoEm` mais recente (a última alteração ganha).
- **Apagar:** envia `apagado: true` (não se apaga de verdade, para propagar aos outros dispositivos). Para apagar basta `id`, `atualizadoEm` e `apagado`.
- Máximo de **500 registos por lista, por pedido**. Em lotes maiores, enviar em vários pedidos.
- Se o relógio do telemóvel estiver mais de 5 minutos adiantado, o `atualizadoEm` é cortado para a hora do servidor.
- Cada conta só vê e altera os seus próprios registos.
- Limite de valor: 999.999.999.999 Kz.

## 3. Deploy (Neon + Render)

### 3.1 Base de dados (Neon)
1. Cria um projecto no Neon e copia a *connection string* (começa por `postgresql://` e termina com `?sslmode=require`).

### 3.2 Email (Brevo)
1. **Chave da API:** Brevo → o teu nome (canto superior direito) → **SMTP & API** → separador **API Keys** → **Generate a new API key**. Copia-a (só aparece uma vez). É uma chave `xkeysib-...` (a chave SMTP é outra coisa).
2. **Remetente:** Brevo → **Senders, Domains & IPs** → **Senders** → adiciona o teu email e confirma-o pelo link que a Brevo envia. Esse email vai em `BREVO_SENDER_EMAIL`.
3. Emails enviados a partir de contas gratuitas (gmail.com, etc.) costumam ir para o spam. Serve para testar. Mais tarde convém um domínio próprio.

### 3.3 Render
1. Põe esta pasta num repositório do GitHub (`.env` e `db.sqlite3` já estão no `.gitignore`).
2. Render → **New → Web Service** → escolhe o repositório.
   - Runtime: Python
   - Build Command: `./build.sh`
   - Start Command: `gunicorn config.wsgi`
3. **Environment** (variáveis):

| Variável | Valor |
|---|---|
| `SECRET_KEY` | uma chave longa e aleatória (ex.: 50+ caracteres) |
| `DEBUG` | `False` |
| `DATABASE_URL` | a string do Neon |
| `CORS_ALLOWED_ORIGINS` | o endereço do front, sem `/` no fim (ex.: `https://cofrinho-ao.vercel.app`) |
| `BREVO_API_KEY` | a chave `xkeysib-...` |
| `BREVO_SENDER_EMAIL` | o remetente validado |
| `BREVO_SENDER_NAME` | `Cofrinho AO` |

   `ALLOWED_HOSTS` não é preciso: o Render fornece o endereço automaticamente.
4. Depois do primeiro deploy, abre `https://<o-teu-servico>.onrender.com/api/saude/`: deve responder `{"estado": "ok"}`.
5. Cria o teu utilizador administrador: no Render, separador **Shell** → `python manage.py createsuperuser`. (Se o Shell não estiver disponível no plano gratuito, corre o mesmo comando no PC com `DATABASE_URL` do Neon definido no `.env`.)
6. Se o email da Brevo ainda não estiver a funcionar, podes marcar uma conta como verificada à mão em `/admin/` (Utilizadores → "email verificado").

Nota: no plano gratuito o serviço "adormece" após alguns minutos parado e o primeiro pedido demora. A app deve tolerar isto (mostrar "a sincronizar…" e tentar de novo).

## 4. Decisões
- Login por token de sessão por dispositivo (não JWT): permite terminar uma sessão sem afectar as outras.
- Senha do servidor: mínimo de 6 caracteres (a app usa 4 hoje; sobe-se para 6 quando ligarmos a app).
- O email não pode ser alterado por agora (exigiria nova verificação).
- Código de email: 6 dígitos, válido 15 min, máximo 5 tentativas, reenvio a cada 60 s.
- Limites de pedidos por IP: `auth` 20/min, `codigo` 5/min, `sync` 60/min.
- `estadoAssinatura` existe no perfil (sempre `"gratuito"`); nada é bloqueado.

## 5. Por fazer (ligar à app)
- Ecrãs Login/Cadastro a usarem esta API; guardar o token no dispositivo (sessão persistente).
- Motor de sincronização na app: enviar o que mudou, aplicar o que chega, tratar offline.
- IDs determinísticos para as categorias padrão, para não duplicarem entre dispositivos.
- Recuperar senha por email no lugar do "recriar conta local".
- Apagar conta e exportar dados (pedido comum de privacidade).
