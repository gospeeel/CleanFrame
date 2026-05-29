<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, shallowRef, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '~/entities/user'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'
import BrandLogo from '~/shared/ui/BrandLogo.vue'

type AuthMode = 'login' | 'register'
type OAuthProvider = 'google' | 'yandex' | 'vk'

const props = withDefaults(defineProps<{
  initialMode?: AuthMode
}>(), {
  initialMode: 'login'
})

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const rootRef = useTemplateRef<HTMLElement>('root')

const mode = shallowRef<AuthMode>(props.initialMode)
const loginOrEmail = shallowRef('')
const login = shallowRef('')
const email = shallowRef('')
const password = shallowRef('')
const confirmPassword = shallowRef('')
const inviteCode = shallowRef(typeof route.query.invite === 'string' ? route.query.invite : '')
const formError = shallowRef('')
const isPasswordVisible = shallowRef(false)
const isConfirmPasswordVisible = shallowRef(false)

const isRegister = computed(() => mode.value === 'register')
const title = computed(() => isRegister.value ? 'Создать рабочий профиль' : 'Войти в рабочее пространство')
const subtitle = computed(() =>
  isRegister.value
    ? 'Регистрация создаёт обычного пользователя. Админ-доступ выдаётся отдельно.'
    : 'Используйте почту, логин или вход через подключённые сервисы.'
)
const redirectTarget = computed(() =>
  typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
    ? route.query.redirect
    : '/'
)

const socialProviders: Array<{ id: OAuthProvider; label: string; mark: string }> = [
  { id: 'google', label: 'Google', mark: 'G' },
  { id: 'yandex', label: 'Yandex', mark: 'Я' },
  { id: 'vk', label: 'VK', mark: 'VK' }
]


function switchMode(nextMode: AuthMode) {
  mode.value = nextMode
  formError.value = ''

  requestAnimationFrame(() => {
    const form = rootRef.value?.querySelector('[data-form-body]')
    if (!form) {
      return
    }

    anime({
      targets: form,
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.microDuration,
      easing: smoothMotion.easing
    })
  })
}

async function submitCredentials() {
  formError.value = ''

  try {
    if (isRegister.value) {
      if (password.value !== confirmPassword.value) {
        formError.value = 'Пароли не совпадают'
        return
      }

      await auth.register({
        login: login.value,
        email: email.value,
        password: password.value,
        confirmPassword: confirmPassword.value,
        inviteToken: inviteCode.value || undefined
      })
      router.replace(redirectTarget.value)
      return
    }

    await auth.login({
      loginOrEmail: loginOrEmail.value,
      password: password.value
    })
    router.replace(redirectTarget.value)
  } catch (error) {
    formError.value = error instanceof Error ? error.message : 'Ошибка авторизации'
  }
}

function submitOAuth(provider: OAuthProvider) {
  auth.loginWithProvider(provider)
}

function togglePasswordVisibility() {
  isPasswordVisible.value = !isPasswordVisible.value
}

function toggleConfirmPasswordVisibility() {
  isConfirmPasswordVisible.value = !isConfirmPasswordVisible.value
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-brand]'),
      translateY: [smoothMotion.largeLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: rootRef.value.querySelector('[data-form]'),
      translateY: [smoothMotion.largeLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    }, '-=540')
    .add({
      targets: rootRef.value.querySelectorAll('[data-field]'),
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0.7, 1],
      delay: anime.stagger(70),
      duration: smoothMotion.microDuration
    }, '-=420')
    .add({
      targets: rootRef.value.querySelectorAll('[data-admin-card]'),
      translateX: [18, 0],
      opacity: [0, 1],
      delay: anime.stagger(80),
      duration: smoothMotion.itemDuration
    }, '-=500')
})
</script>

<template>
  <section ref="root" class="auth-page page-shell">
    <div data-brand class="auth-copy">
      <p class="auth-kicker">Защищённый вход</p>
      <h1 class="auth-title font-display">
        {{ title }}
      </h1>
      <p class="auth-subtitle">{{ subtitle }}</p>
    </div>

    <div data-form class="auth-card glass-panel">
      <div class="auth-card-head">
        <div>
          <h2 class="auth-card-title font-display">
            {{ isRegister ? 'Регистрация' : 'Вход' }}
          </h2>
        </div>
        <BrandLogo :show-text="false" size="sm" class="auth-mark" />
      </div>

      <div data-field class="auth-tabs">
        <button
          class="auth-tab"
          :class="{ 'auth-tab-active': !isRegister }"
          type="button"
          @click="switchMode('login')"
        >
          Вход
        </button>
        <button
          class="auth-tab"
          :class="{ 'auth-tab-active': isRegister }"
          type="button"
          @click="switchMode('register')"
        >
          Регистрация
        </button>
      </div>

      <div data-form-body>
        <form class="auth-form" @submit.prevent="submitCredentials">
          <template v-if="!isRegister">
            <label data-field class="auth-field" for="login-or-email">
              <span class="auth-label">Логин или почта</span>
              <input
                id="login-or-email"
                v-model="loginOrEmail"
                autocomplete="username"
                class="auth-input"
                placeholder="name или name@mail.ru"
                required
                type="text"
              >
            </label>
          </template>

          <template v-else>
            <label data-field class="auth-field" for="login">
              <span class="auth-label">Логин</span>
              <input
                id="login"
                v-model="login"
                autocomplete="username"
                class="auth-input"
                placeholder="cf_analyst"
                required
                type="text"
              >
            </label>

            <label data-field class="auth-field" for="email">
              <span class="auth-label">Почта</span>
              <input
                id="email"
                v-model="email"
                autocomplete="email"
                class="auth-input"
                placeholder="name@mail.ru"
                required
                type="email"
              >
            </label>
          </template>

          <label data-field class="auth-field" for="password">
            <span class="auth-label">Пароль</span>
            <span class="password-control">
              <input
                id="password"
                v-model="password"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                class="auth-input password-input"
                placeholder="Минимум 8 символов"
                required
                minlength="8"
                :type="isPasswordVisible ? 'text' : 'password'"
              >
              <button
                class="password-toggle"
                type="button"
                :aria-label="isPasswordVisible ? 'Скрыть пароль' : 'Показать пароль'"
                @click="togglePasswordVisibility"
              >
                <span class="eye-icon" :class="{ 'eye-icon-hidden': isPasswordVisible }" />
              </button>
            </span>
          </label>

          <label v-if="isRegister" data-field class="auth-field" for="confirm-password">
            <span class="auth-label">Повторите пароль</span>
            <span class="password-control">
              <input
                id="confirm-password"
                v-model="confirmPassword"
                autocomplete="new-password"
                class="auth-input password-input"
                placeholder="Ещё раз пароль"
                required
                minlength="8"
                :type="isConfirmPasswordVisible ? 'text' : 'password'"
              >
              <button
                class="password-toggle"
                type="button"
                :aria-label="isConfirmPasswordVisible ? 'Скрыть подтверждение пароля' : 'Показать подтверждение пароля'"
                @click="toggleConfirmPasswordVisibility"
              >
                <span class="eye-icon" :class="{ 'eye-icon-hidden': isConfirmPasswordVisible }" />
              </button>
            </span>
          </label>

          <label v-if="isRegister" data-field class="auth-field" for="invite-code">
            <span class="auth-label">Пригласительная ссылка или код</span>
            <input
              id="invite-code"
              v-model="inviteCode"
              class="auth-input"
              placeholder="Опционально"
              type="text"
            >
          </label>

          <p v-if="formError" class="auth-error">
            {{ formError }}
          </p>

          <div v-if="!isRegister" data-field class="auth-row">
            <label class="auth-checkbox">
              <input type="checkbox">
              Запомнить меня
            </label>
            <NuxtLink class="auth-link" to="/login">
              Забыли пароль?
            </NuxtLink>
          </div>

          <button
            data-field
            class="auth-submit"
            type="submit"
          >
            {{ isRegister ? 'Создать аккаунт' : 'Войти' }}
          </button>
        </form>

        <div class="auth-divider">
          <span />
          <span>Вход через сервисы</span>
          <span />
        </div>

        <div class="oauth-grid">
          <button
            v-for="provider in socialProviders"
            :key="provider.id"
            class="oauth-button"
            type="button"
            @click="submitOAuth(provider.id)"
          >
            <span class="oauth-mark">
              {{ provider.mark }}
            </span>
            <span>{{ provider.label }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.auth-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 520px);
  align-items: start;
  gap: clamp(28px, 4vw, 64px);
  position: relative;
}

.auth-copy {
  max-width: 820px;
  padding-left: clamp(12px, 3vw, 56px);
  opacity: 0;
}

.auth-kicker,
.auth-card-kicker {
  color: var(--color-blue);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.24em;
  text-transform: uppercase;
}

.auth-card-kicker {
  color: var(--color-muted);
  letter-spacing: 0.22em;
}

.auth-title {
  max-width: 800px;
  margin-top: 18px;
  color: var(--color-ink);
  font-size: clamp(48px, 4.4vw, 82px);
  font-weight: 600;
  line-height: 0.96;
  letter-spacing: 0;
}

.auth-subtitle {
  max-width: 620px;
  margin-top: 20px;
  color: var(--color-muted);
  font-size: 16px;
  line-height: 1.7;
}

.admin-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  max-width: 820px;
  margin-top: 34px;
}

.admin-card {
  position: relative;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 250, 241, 0.68);
  padding: 18px;
  opacity: 0;
  box-shadow: 0 16px 46px rgba(42, 48, 44, 0.1);
  overflow: hidden;
}

.admin-card::before {
  position: absolute;
  top: 0;
  left: 18px;
  right: 18px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--color-coral), var(--color-brass), var(--color-blue));
  content: "";
  opacity: 0.75;
}

.admin-card-title {
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 800;
}

.admin-card-text {
  margin-top: 8px;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.55;
}

.auth-card {
  position: relative;
  width: 100%;
  max-width: 520px;
  justify-self: end;
  border-radius: var(--radius-panel);
  padding: clamp(24px, 2.6vw, 36px);
  opacity: 0;
  overflow: hidden;
}

.auth-card::before {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(140deg, rgba(184, 146, 93, 0.12), transparent 34%),
    linear-gradient(320deg, rgba(82, 111, 122, 0.1), transparent 28%);
  content: "";
  pointer-events: none;
}

.auth-card > * {
  position: relative;
}

.auth-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.auth-card-title {
  margin-top: 8px;
  color: var(--color-ink);
  font-size: clamp(30px, 2.6vw, 40px);
  font-weight: 600;
  line-height: 1;
}

.oauth-mark {
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: var(--color-blue);
  color: var(--color-paper);
  font-weight: 800;
}

.auth-mark {
  width: 48px;
  height: 48px;
  box-shadow: 0 14px 30px rgba(82, 111, 122, 0.2);
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: rgba(255, 250, 241, 0.72);
  padding: 4px;
}

.auth-tab {
  min-width: 0;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-muted);
  padding: 12px 10px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  transition: background 160ms ease, color 160ms ease;
}

.auth-tab-active {
  background: linear-gradient(135deg, var(--color-blue), #668390);
  color: var(--color-paper);
  box-shadow: 0 14px 34px rgba(82, 111, 122, 0.18);
}

.auth-form {
  display: grid;
  gap: 16px;
  margin-top: 20px;
}

.auth-field {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.auth-label {
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 800;
}

.auth-input {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: rgba(255, 250, 241, 0.76);
  color: var(--color-ink);
  padding: 13px 14px;
  font-size: 15px;
  font-weight: 700;
  outline: none;
  transition: border-color 160ms ease, background 160ms ease;
}

.auth-input::placeholder {
  color: rgba(105, 113, 111, 0.65);
}

.auth-input:focus {
  border-color: var(--color-blue);
  background: white;
  box-shadow: 0 0 0 4px rgba(82, 111, 122, 0.12);
}

.password-control {
  position: relative;
  display: block;
}

.password-input {
  padding-right: 48px;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 8px;
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-muted);
  transform: translateY(-50%);
  transition: background 160ms ease, color 160ms ease;
}

.password-toggle:hover {
  background: rgba(82, 111, 122, 0.12);
  color: var(--color-ink);
}

.eye-icon {
  position: relative;
  width: 18px;
  height: 12px;
  border: 2px solid currentColor;
  border-radius: 999px / 740px;
}

.eye-icon::before {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
  content: "";
  transform: translate(-50%, -50%);
}

.eye-icon::after {
  position: absolute;
  top: 50%;
  left: -2px;
  width: 22px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  content: "";
  opacity: 0;
  transform: rotate(-38deg) scaleX(0.7);
  transition: opacity 160ms ease, transform 160ms ease;
}

.eye-icon-hidden::after {
  opacity: 1;
  transform: rotate(-38deg) scaleX(1);
}

.auth-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.auth-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-muted);
  font-size: 14px;
  font-weight: 700;
}

.auth-checkbox input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-blue);
}

.auth-link {
  color: var(--color-coral);
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
}

.auth-error {
  border: 1px solid rgba(201, 111, 88, 0.4);
  border-radius: var(--radius-control);
  background: rgba(201, 111, 88, 0.1);
  color: var(--color-coral);
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 800;
}

.auth-submit {
  width: 100%;
  border: 0;
  border-radius: var(--radius-control);
  background: linear-gradient(135deg, var(--color-blue), #668390);
  color: var(--color-paper);
  padding: 15px 18px;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  box-shadow: 0 18px 46px rgba(82, 111, 122, 0.18);
  transition: transform 160ms ease, background 160ms ease;
}

.auth-submit:hover {
  background: linear-gradient(135deg, var(--color-coral), var(--color-brass));
  transform: translateY(-2px);
}

.auth-divider {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  margin-block: 20px;
}

.auth-divider span:first-child,
.auth-divider span:last-child {
  height: 1px;
  background: var(--line);
}

.auth-divider span:nth-child(2) {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.oauth-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.oauth-button {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: rgba(255, 250, 241, 0.72);
  color: var(--color-ink);
  padding: 12px 10px;
  font-size: 14px;
  font-weight: 800;
  transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
}

.oauth-button:hover {
  border-color: var(--color-blue);
  background: white;
  transform: translateY(-2px);
}

.oauth-mark {
  min-width: 24px;
  height: 24px;
  padding-inline: 4px;
  font-size: 11px;
  line-height: 1;
}

@media (max-width: 1180px) {
  .auth-page {
    grid-template-columns: minmax(0, 1fr);
  }

  .auth-copy {
    max-width: none;
    padding-left: 0;
  }

  .auth-card {
    justify-self: stretch;
    max-width: 640px;
  }
}

@media (max-width: 760px) {
  .auth-title {
    font-size: clamp(40px, 12vw, 56px);
  }

  .admin-grid,
  .oauth-grid {
    grid-template-columns: 1fr;
  }

  .auth-card {
    padding: 20px;
  }
}
</style>
