# Auth database

Связей many-to-many нет. Все связи явные one-to-many или optional one-to-one по смыслу использования invite.

```mermaid
erDiagram
  USERS {
    uuid id PK
    varchar login UK
    varchar email UK
    datetime email_verified_at
    varchar avatar_url
    string password_hash
    UserRole role
    boolean is_active
    datetime created_at
    datetime updated_at
  }

  AUTH_ACCOUNTS {
    uuid id PK
    uuid user_id FK
    OAuthProvider provider
    varchar provider_account_id
    varchar email
    datetime created_at
  }

  REFRESH_TOKENS {
    uuid id PK
    uuid user_id FK
    string token_hash UK
    datetime expires_at
    datetime revoked_at
    datetime created_at
  }

  EMAIL_VERIFICATION_CODES {
    uuid id PK
    uuid user_id FK
    varchar target_email
    string code_hash
    EmailVerificationPurpose purpose
    datetime expires_at
    datetime used_at
    datetime created_at
  }

  ADMIN_INVITES {
    uuid id PK
    string token_hash UK
    UserRole role
    datetime expires_at
    datetime used_at
    datetime created_at
    uuid created_by FK
    uuid used_by FK
  }

  OAUTH_STATES {
    uuid id PK
    uuid user_id FK
    OAuthProvider provider
    string state_hash UK
    string code_verifier
    string redirect_to
    datetime expires_at
    datetime used_at
    datetime created_at
  }

  USERS ||--o{ AUTH_ACCOUNTS : owns
  USERS ||--o{ REFRESH_TOKENS : has
  USERS ||--o{ EMAIL_VERIFICATION_CODES : requests
  USERS ||--o{ ADMIN_INVITES : creates
  USERS ||--o{ ADMIN_INVITES : uses
  USERS ||--o{ OAUTH_STATES : starts
```

## Таблицы

`users` хранит локальных пользователей, роль, статус подтверждения почты и ссылку на аватар. `password_hash` nullable, потому что OAuth-only пользователь может не иметь локального пароля. Роли: `ANALYST`, `ADMIN`, `SUPER_ADMIN`; `SUPER_ADMIN` создаётся seed-скриптом.

`auth_accounts` хранит внешние аккаунты Google/Yandex/VK. Один внешний аккаунт принадлежит одному пользователю. Уникальность: `(provider, provider_account_id)`.

`refresh_tokens` хранит только SHA-256 hash refresh token. Ротация refresh token выполняется при каждом `/api/auth/refresh`.

`email_verification_codes` оставлена как историческая таблица для возможного будущего подтверждения почты. Текущий runtime не отправляет SMTP-коды и не даёт пользователю менять email из личного кабинета.

`admin_invites` хранит одноразовые invite-link для создания администратора. В БД сохраняется только hash токена, а чистый token возвращается только один раз при создании. `created_by` и `used_by` используются для ограничения прав invite-администраторов.

`oauth_states` хранит короткоживущий OAuth `state`, чтобы callback нельзя было подделать или переиспользовать.
