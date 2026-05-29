<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, reactive, shallowRef, useTemplateRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore, type UserRole } from '~/entities/user'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'
import { useProfileQueries } from '../api/useProfileQueries'
import type { AdminUser } from '../model/types'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const rootRef = useTemplateRef<HTMLElement>('root')
const avatarInputRef = useTemplateRef<HTMLInputElement>('avatarInput')

const {
  adminUsersQuery,
  createInviteMutation,
  updateRoleMutation,
  banUserMutation,
  unbanUserMutation,
  deleteUserMutation,
  changePasswordMutation,
  uploadAvatarMutation
} = useProfileQueries()

const inviteHours = shallowRef(24)
const copiedInvite = shallowRef(false)
const avatarError = shallowRef('')
const passwordError = shallowRef('')
const passwordSuccess = shallowRef('')
const confirmAction = shallowRef<{
  title: string
  message: string
  confirmText: string
  tone: 'default' | 'danger'
  run: () => Promise<void>
} | null>(null)

const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const isAdmin = computed(() => user.value?.role === 'ADMIN' || user.value?.role === 'SUPER_ADMIN')
const adminUsers = computed(() => adminUsersQuery.data.value ?? [])
const invite = computed(() => createInviteMutation.data.value ?? null)
const inviteLink = computed(() => {
  if (!invite.value || !process.client) {
    return ''
  }

  return `${window.location.origin}/register?invite=${invite.value.token}`
})

const profileRows = computed(() => [
  { label: 'Логин', value: user.value?.login ?? '-' },
  { label: 'Почта', value: user.value?.email ?? '-' },
  { label: 'Роль', value: formatRole(user.value?.role) },
  { label: 'Статус', value: user.value?.isActive ? 'Активен' : 'Отключён' },
  { label: 'Создан', value: user.value?.createdAt ? formatDate(user.value.createdAt) : '-' }
])

function formatRole(role?: UserRole) {
  if (role === 'SUPER_ADMIN') return 'Главный администратор'
  if (role === 'ADMIN') return 'Администратор'
  if (role === 'ANALYST') return 'Пользователь'
  return '-'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value))
}

function openAvatarPicker() {
  avatarInputRef.value?.click()
}

async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  avatarError.value = ''
  try {
    await uploadAvatarMutation.mutateAsync(file)
  } catch {
    avatarError.value = 'Не удалось обновить фото профиля'
  } finally {
    if (avatarInputRef.value) {
      avatarInputRef.value.value = ''
    }
  }
}

async function changePassword() {
  passwordError.value = ''
  passwordSuccess.value = ''
  try {
    await changePasswordMutation.mutateAsync({ ...passwordForm })
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    passwordSuccess.value = 'Пароль обновлён'
  } catch {
    passwordError.value = 'Не удалось обновить пароль'
  }
}

async function createInvite() {
  copiedInvite.value = false
  await createInviteMutation.mutateAsync(inviteHours.value)
}

async function copyInviteLink() {
  if (!inviteLink.value || !navigator.clipboard) {
    return
  }

  await navigator.clipboard.writeText(inviteLink.value)
  copiedInvite.value = true
  window.setTimeout(() => {
    copiedInvite.value = false
  }, 2200)
}

function updateRole(targetUser: AdminUser, role: UserRole) {
  if (targetUser.role === role) return
  confirmAction.value = {
    title: 'Подтвердите смену роли',
    message: `Изменить роль пользователя ${targetUser.login} на «${formatRole(role)}»?`,
    confirmText: 'Изменить роль',
    tone: 'default',
    run: async () => {
      await updateRoleMutation.mutateAsync({ userId: targetUser.id, role })
    }
  }
}

function banUser(targetUser: AdminUser) {
  confirmAction.value = {
    title: 'Заблокировать аккаунт',
    message: `Пользователь ${targetUser.login} потеряет доступ к сервису, активные сессии будут отозваны.`,
    confirmText: 'Заблокировать',
    tone: 'danger',
    run: async () => {
      await banUserMutation.mutateAsync(targetUser.id)
    }
  }
}

function unbanUser(targetUser: AdminUser) {
  confirmAction.value = {
    title: 'Разблокировать аккаунт',
    message: `Вернуть пользователю ${targetUser.login} доступ к сервису?`,
    confirmText: 'Разблокировать',
    tone: 'default',
    run: async () => {
      await unbanUserMutation.mutateAsync(targetUser.id)
    }
  }
}

function deleteUser(targetUser: AdminUser) {
  confirmAction.value = {
    title: 'Удалить аккаунт',
    message: `Аккаунт ${targetUser.login} будет удалён без восстановления. Это самая строгая мера модерации.`,
    confirmText: 'Удалить аккаунт',
    tone: 'danger',
    run: async () => {
      await deleteUserMutation.mutateAsync(targetUser.id)
    }
  }
}

async function confirmModerationAction() {
  if (!confirmAction.value) return
  const action = confirmAction.value
  await action.run()
  confirmAction.value = null
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-profile-hero]'),
      translateY: [smoothMotion.largeLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: rootRef.value.querySelectorAll('[data-profile-card]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
})
</script>

<template>
  <section ref="root" class="page-shell profile-page">
    <div data-profile-hero class="profile-hero glass-panel opacity-0">
      <div>
        <p class="profile-kicker">Личный кабинет</p>
        <h1 class="profile-heading font-display">Профиль и настройки</h1>
        <p class="profile-lead">
          Управляйте данными аккаунта, фото профиля и доступами команды в одном рабочем разделе.
        </p>
      </div>
      <div class="profile-avatar" :class="{ 'profile-avatar-image': user?.avatarUrl }">
        <img v-if="user?.avatarUrl" :src="user.avatarUrl" alt="">
        <span v-else>{{ user?.login?.slice(0, 2).toUpperCase() ?? 'CK' }}</span>
        <small>{{ formatRole(user?.role) }}</small>
      </div>
    </div>

    <div class="profile-grid">
      <article data-profile-card class="profile-card glass-panel opacity-0">
        <p class="profile-kicker">Аккаунт</p>
        <h2 class="profile-title font-display">Основные данные</h2>
        <dl class="profile-rows">
          <div v-for="row in profileRows" :key="row.label" class="profile-row">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>
      </article>

      <article data-profile-card class="profile-card glass-panel opacity-0">
        <p class="profile-kicker">Настройки</p>
        <h2 class="profile-title font-display">Настройки аккаунта</h2>
        <div class="settings-stack">
          <div class="avatar-tools">
            <div class="avatar-current" :class="{ 'avatar-current-image': user?.avatarUrl }">
              <img v-if="user?.avatarUrl" :src="user.avatarUrl" alt="">
              <span v-else>{{ user?.login?.slice(0, 2).toUpperCase() ?? 'CK' }}</span>
            </div>
            <button class="profile-button" type="button" :disabled="uploadAvatarMutation.isPending.value" @click="openAvatarPicker">
              Заменить фото
            </button>
            <input ref="avatarInput" class="sr-only" accept="image/*" type="file" @change="uploadAvatar">
          </div>
          <p v-if="avatarError" class="profile-error">{{ avatarError }}</p>

          <form class="password-grid" @submit.prevent="changePassword">
            <label>
              <span>Текущий пароль</span>
              <input v-model="passwordForm.currentPassword" autocomplete="current-password" type="password">
            </label>
            <label>
              <span>Новый пароль</span>
              <input v-model="passwordForm.newPassword" autocomplete="new-password" type="password">
            </label>
            <label>
              <span>Повторите пароль</span>
              <input v-model="passwordForm.confirmPassword" autocomplete="new-password" type="password">
            </label>
            <button class="profile-button" type="submit" :disabled="changePasswordMutation.isPending.value">
              Сменить пароль
            </button>
          </form>
          <p v-if="passwordSuccess" class="profile-success">{{ passwordSuccess }}</p>
          <p v-if="passwordError" class="profile-error">{{ passwordError }}</p>
        </div>
      </article>
    </div>

    <section v-if="isAdmin" data-profile-card class="admin-panel glass-panel opacity-0">
      <div class="admin-head">
        <div>
          <p class="profile-kicker">Панель администратора</p>
          <h2 class="profile-title font-display">Управление доступами</h2>
        </div>
      </div>

      <div class="invite-box">
        <div class="invite-controls">
          <div class="invite-note">
            <span>Пригласительная ссылка</span>
            <strong>Создаёт профиль администратора</strong>
          </div>
          <label>
            <span>Срок действия, часов</span>
            <input v-model.number="inviteHours" min="1" max="336" type="number">
          </label>
          <button class="profile-button" type="button" :disabled="createInviteMutation.isPending.value" @click="createInvite">
            Создать ссылку
          </button>
        </div>

        <p v-if="createInviteMutation.isError.value" class="profile-error">Не удалось создать пригласительную ссылку</p>
        <div v-if="invite" class="invite-result">
          <span>{{ inviteLink }}</span>
          <button type="button" @click="copyInviteLink">{{ copiedInvite ? 'Скопировано' : 'Скопировать' }}</button>
        </div>
      </div>

      <p
        v-if="adminUsersQuery.isError.value || updateRoleMutation.isError.value || banUserMutation.isError.value || unbanUserMutation.isError.value || deleteUserMutation.isError.value"
        class="profile-error"
      >
        Не удалось обновить данные пользователей
      </p>
      <div class="users-table">
        <div class="users-head">
          <span>Пользователь</span>
          <span>Роль</span>
          <span>Статус</span>
          <span>Создан</span>
          <span>Действия</span>
        </div>
        <div v-for="item in adminUsers" :key="item.id" class="users-row">
          <div>
            <strong>{{ item.login }}</strong>
            <small>{{ item.email }}</small>
          </div>
          <select
            :value="item.role"
            :disabled="!item.canChangeRole"
            @change="updateRole(item, ($event.target as HTMLSelectElement).value as UserRole)"
          >
            <option value="ANALYST">Пользователь</option>
            <option value="ADMIN">Администратор</option>
            <option value="SUPER_ADMIN">Главный администратор</option>
          </select>
          <span>{{ item.isActive ? 'Активен' : 'Отключён' }}</span>
          <span>{{ formatDate(item.createdAt) }}</span>
          <div class="moderation-actions">
            <button v-if="item.canBan" type="button" @click="banUser(item)">Забанить</button>
            <button v-if="item.canUnban" type="button" @click="unbanUser(item)">Разбанить</button>
            <button v-if="item.canDelete" class="danger" type="button" @click="deleteUser(item)">Удалить</button>
            <span v-if="!item.canBan && !item.canUnban && !item.canDelete">Недоступно</span>
          </div>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="confirmAction" class="confirm-backdrop" @click.self="confirmAction = null">
        <div class="confirm-dialog" role="dialog" aria-modal="true">
          <p class="profile-kicker">Подтверждение</p>
          <h2 class="profile-title font-display">{{ confirmAction.title }}</h2>
          <p class="confirm-message">{{ confirmAction.message }}</p>
          <div class="confirm-actions">
            <button class="profile-button profile-button-secondary" type="button" @click="confirmAction = null">
              Отмена
            </button>
            <button
              class="profile-button"
              :class="{ 'profile-button-danger': confirmAction.tone === 'danger' }"
              type="button"
              @click="confirmModerationAction"
            >
              {{ confirmAction.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.profile-page {
  display: grid;
  gap: 20px;
}

.profile-hero,
.profile-card,
.admin-panel {
  position: relative;
  overflow: hidden;
  padding: clamp(22px, 3vw, 40px);
}

.profile-hero {
  display: flex;
  min-height: 300px;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
}

.profile-heading {
  margin-top: 14px;
  color: var(--color-ink);
  font-size: clamp(2.5rem, 5vw, 5rem);
  font-weight: 600;
  line-height: 0.98;
}

.profile-lead {
  margin-top: 20px;
  max-width: 680px;
  color: var(--color-muted);
  font-size: 16px;
  line-height: 1.75;
}

.profile-avatar {
  display: grid;
  width: 140px;
  height: 140px;
  flex: 0 0 auto;
  place-items: center;
  overflow: hidden;
  border: 1px solid rgba(82, 111, 122, 0.24);
  border-radius: 30px;
  background: rgba(255, 250, 241, 0.58);
  box-shadow: 0 18px 48px rgba(82, 111, 122, 0.12);
}

.profile-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-avatar span {
  font-size: 38px;
  font-weight: 900;
  color: var(--color-blue);
}

.profile-avatar small {
  margin-top: -34px;
  color: var(--color-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.profile-avatar-image small {
  display: none;
}

.profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.82fr) minmax(420px, 1fr);
  gap: 20px;
}

.profile-kicker {
  color: var(--color-blue);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}

.profile-title {
  margin-top: 10px;
  color: var(--color-ink);
  font-size: clamp(30px, 3vw, 44px);
  font-weight: 600;
  line-height: 1;
}

.profile-rows,
.settings-stack {
  display: grid;
  gap: 14px;
  margin-top: 26px;
}

.profile-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
}

.profile-row dt {
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
}

.profile-row dd {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--color-ink);
  font-weight: 900;
  text-align: right;
}

.avatar-tools,
.settings-form,
.password-grid,
.invite-controls {
  display: grid;
  gap: 12px;
}

.avatar-tools {
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: center;
}

.avatar-current {
  display: grid;
  width: 96px;
  height: 96px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: rgba(255, 250, 241, 0.72);
  color: var(--color-blue);
  font-weight: 900;
}

.avatar-current img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.settings-form {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
}

.password-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  align-items: end;
}

.settings-form label,
.password-grid label,
.invite-controls label {
  display: grid;
  gap: 8px;
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.settings-form input,
.password-grid input,
.invite-controls input,
.users-row select {
  min-height: 48px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: rgba(255, 250, 241, 0.8);
  color: var(--color-ink);
  font-weight: 800;
  outline: none;
  padding-inline: 14px;
}

.settings-form input:focus,
.password-grid input:focus,
.invite-controls input:focus,
.users-row select:focus {
  border-color: var(--color-blue);
  box-shadow: 0 0 0 4px rgba(82, 111, 122, 0.1);
}

.admin-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 20px;
}

.invite-box {
  margin-top: 28px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 250, 241, 0.52);
  padding: 16px;
}

.invite-controls {
  grid-template-columns: minmax(260px, 1fr) 220px auto;
  align-items: end;
}

.invite-note {
  display: grid;
  gap: 8px;
}

.invite-note span {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.invite-note strong {
  color: var(--color-ink);
  font-size: 15px;
}

.profile-button {
  min-height: 48px;
  border-radius: var(--radius-control);
  background: var(--color-blue);
  padding: 0 18px;
  color: var(--color-paper);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  transition: transform 240ms ease, background 240ms ease;
}

.profile-button:hover {
  transform: translateY(-1px);
  background: var(--color-coral);
}

.profile-button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.profile-button-secondary {
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.72);
  color: var(--color-ink);
}

.profile-button-danger {
  background: var(--color-coral);
}

.invite-result {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
}

.invite-result span {
  min-width: 0;
  flex: 1;
  overflow-wrap: anywhere;
  border-radius: 12px;
  background: rgba(82, 111, 122, 0.1);
  padding: 12px;
  color: var(--color-ink);
  font-size: 13px;
  font-weight: 800;
}

.invite-result button {
  border-radius: 12px;
  background: var(--color-brass);
  padding: 12px 14px;
  color: var(--color-paper);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.profile-error,
.profile-success {
  color: var(--color-coral);
  font-size: 13px;
  font-weight: 900;
}

.profile-success {
  color: var(--color-blue);
}

.users-table {
  display: grid;
  gap: 0;
  margin-top: 22px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 18px;
}

.users-head,
.users-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 170px 130px 170px 260px;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
}

.users-head {
  background: rgba(82, 111, 122, 0.1);
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.users-row {
  border-top: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.42);
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 800;
}

.users-row strong,
.users-row small {
  display: block;
}

.users-row strong {
  color: var(--color-ink);
  font-size: 14px;
}

.users-row small {
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.moderation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.moderation-actions button {
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.72);
  padding: 9px 10px;
  color: var(--color-ink);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
  transition: border-color 180ms ease, color 180ms ease;
}

.moderation-actions button:hover {
  border-color: var(--color-blue);
  color: var(--color-blue);
}

.moderation-actions button.danger {
  color: var(--color-coral);
}

.moderation-actions span {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
}

.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(28, 33, 31, 0.34);
  backdrop-filter: blur(14px);
}

.confirm-dialog {
  width: min(520px, 100%);
  border: 1px solid var(--line);
  border-radius: 24px;
  background: rgba(255, 250, 241, 0.96);
  box-shadow: 0 28px 80px rgba(28, 33, 31, 0.22);
  padding: 28px;
}

.confirm-message {
  margin-top: 16px;
  color: var(--color-muted);
  font-size: 15px;
  line-height: 1.7;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}

@media (max-width: 1100px) {
  .profile-grid,
  .settings-form,
  .password-grid,
  .invite-controls {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .profile-hero,
  .admin-head,
  .invite-result {
    align-items: stretch;
    flex-direction: column;
  }

  .avatar-tools {
    grid-template-columns: minmax(0, 1fr);
  }

  .users-table {
    overflow-x: auto;
  }

  .users-head,
  .users-row {
    min-width: 980px;
  }
}
</style>
