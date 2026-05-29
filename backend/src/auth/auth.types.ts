import { OAuthProvider, UserRole } from '@prisma/client'
import { Request } from 'express'

export interface JwtUser {
  sub: string
  login: string
  email: string
  role: UserRole
}

export interface AuthRequest extends Request {
  user?: JwtUser
}

export interface RegisterDto {
  login?: string
  email?: string
  password?: string
  confirmPassword?: string
  inviteToken?: string
}

export interface LoginDto {
  loginOrEmail?: string
  password?: string
}

export interface RefreshDto {
  refreshToken?: string
}

export interface CreateInviteDto {
  expiresInHours?: number
  role?: UserRole
}

export interface PromoteUserDto {
  role?: UserRole
}

export interface ChangePasswordDto {
  currentPassword?: string
  newPassword?: string
  confirmPassword?: string
}

export interface OAuthProfile {
  provider: OAuthProvider
  providerAccountId: string
  email?: string
  login?: string
}
