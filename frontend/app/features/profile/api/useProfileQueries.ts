import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { useRuntimeConfig } from '#app'
import { useAuthStore } from '~/entities/user'
import type { ChangePasswordPayload, ConfirmEmailChangePayload, RequestEmailChangePayload, UserRole } from '../model/types'
import {
  banUser,
  changePassword,
  confirmEmailChange,
  createAdminInvite,
  deleteUser,
  deleteAvatar,
  fetchAdminUsers,
  requestEmailChange,
  unbanUser,
  updateUserRole,
  uploadAvatar
} from './profileApi'

export function useProfileQueries() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const queryClient = useQueryClient()
  const apiBase = computed(() => config.public.apiBase)
  const clientOptions = computed(() => ({
    apiBase: apiBase.value,
    token: auth.token
  }))

  const adminUsersQuery = useQuery({
    queryKey: computed(() => ['admin-users', auth.user?.id]),
    enabled: computed(() => (auth.user?.role === 'ADMIN' || auth.user?.role === 'SUPER_ADMIN') && Boolean(auth.token)),
    queryFn: () => fetchAdminUsers(clientOptions.value)
  })

  const createInviteMutation = useMutation({
    mutationFn: (expiresInHours: number) => createAdminInvite(clientOptions.value, expiresInHours)
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      updateUserRole(clientOptions.value, userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })
  })

  const banUserMutation = useMutation({
    mutationFn: (userId: string) => banUser(clientOptions.value, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })
  })

  const unbanUserMutation = useMutation({
    mutationFn: (userId: string) => unbanUser(clientOptions.value, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })
  })

  const deleteUserMutation = useMutation({
    mutationFn: (userId: string) => deleteUser(clientOptions.value, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })
  })

  const requestEmailMutation = useMutation({
    mutationFn: (payload: RequestEmailChangePayload) => requestEmailChange(clientOptions.value, payload)
  })

  const confirmEmailMutation = useMutation({
    mutationFn: (payload: ConfirmEmailChangePayload) => confirmEmailChange(clientOptions.value, payload),
    onSuccess: (session) => {
      auth.applySession(session)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    }
  })

  const changePasswordMutation = useMutation({
    mutationFn: (payload: ChangePasswordPayload) => changePassword(clientOptions.value, payload)
  })

  const uploadAvatarMutation = useMutation({
    mutationFn: (file: File) => uploadAvatar(clientOptions.value, file),
    onSuccess: (user) => {
      auth.applyUser(user)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    }
  })

  const deleteAvatarMutation = useMutation({
    mutationFn: () => deleteAvatar(clientOptions.value),
    onSuccess: (user) => {
      auth.applyUser(user)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    }
  })

  return {
    adminUsersQuery,
    createInviteMutation,
    updateRoleMutation,
    banUserMutation,
    unbanUserMutation,
    deleteUserMutation,
    requestEmailMutation,
    confirmEmailMutation,
    changePasswordMutation,
    uploadAvatarMutation,
    deleteAvatarMutation
  }
}
