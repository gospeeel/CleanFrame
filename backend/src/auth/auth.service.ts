import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
  UnauthorizedException
} from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import { JwtService } from '@nestjs/jwt'
import { EmailVerificationPurpose, OAuthProvider, User, UserRole } from '@prisma/client'
import axios from 'axios'
import * as bcrypt from 'bcryptjs'
import { randomBytes, createHash } from 'node:crypto'
import { PrismaService } from '../prisma/prisma.service'
import { AvatarStorageService } from './avatar-storage.service'
import {
  ChangePasswordDto,
  ConfirmEmailChangeDto,
  CreateInviteDto,
  JwtUser,
  LoginDto,
  OAuthProfile,
  PromoteUserDto,
  RefreshDto,
  RegisterDto,
  RequestEmailChangeDto
} from './auth.types'
import { EmailService } from './email.service'

const ACCESS_TTL_SECONDS = 15 * 60
const REFRESH_TTL_DAYS = 30
const OAUTH_STATE_TTL_MINUTES = 10
const EMAIL_CODE_TTL_MINUTES = 10

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly avatarStorageService: AvatarStorageService,
    private readonly emailService: EmailService
  ) {}

  async register(dto: RegisterDto) {
    const login = this.requireLogin(dto.login)
    const email = this.requireEmail(dto.email)
    const password = this.requirePassword(dto.password)

    if (password !== dto.confirmPassword) {
      throw new BadRequestException('Пароли не совпадают')
    }

    const existingUser = await this.prisma.user.findFirst({
      where: {
        OR: [{ login }, { email }]
      }
    })

    if (existingUser) {
      throw new ConflictException('Пользователь с таким логином или почтой уже существует')
    }

    const passwordHash = await bcrypt.hash(password, 12)
    const invite = dto.inviteToken ? await this.getActiveInvite(dto.inviteToken) : null

    const user = await this.prisma.$transaction(async (tx) => {
      const createdUser = await tx.user.create({
        data: {
          login,
          email,
          passwordHash,
          role: invite?.role ?? UserRole.ANALYST
        }
      })

      if (invite) {
        const usedInvite = await tx.adminInvite.updateMany({
          where: {
            id: invite.id,
            usedAt: null,
            expiresAt: {
              gt: new Date()
            }
          },
          data: {
            usedAt: new Date(),
            usedBy: createdUser.id
          }
        })

        if (usedInvite.count !== 1) {
          throw new ForbiddenException('Invite-link недействителен или уже использован')
        }
      }

      return createdUser
    })

    return this.issueSession(user)
  }

  async login(dto: LoginDto) {
    const loginOrEmail = this.requireString(dto.loginOrEmail, 'Логин или почта обязательны')
      .toLowerCase()
    const password = this.requireString(dto.password, 'Пароль обязателен')

    const user = await this.prisma.user.findFirst({
      where: {
        OR: [{ login: loginOrEmail }, { email: loginOrEmail }]
      }
    })

    if (!user?.passwordHash || !user.isActive) {
      throw new UnauthorizedException('Неверный логин или пароль')
    }

    const isPasswordValid = await bcrypt.compare(password, user.passwordHash)
    if (!isPasswordValid) {
      throw new UnauthorizedException('Неверный логин или пароль')
    }

    return this.issueSession(user)
  }

  async refresh(dto: RefreshDto) {
    const refreshToken = this.requireString(dto.refreshToken, 'Refresh token обязателен')
    const tokenHash = this.hashToken(refreshToken)
    const storedToken = await this.prisma.refreshToken.findUnique({
      where: { tokenHash },
      include: { user: true }
    })

    if (
      !storedToken ||
      storedToken.revokedAt ||
      storedToken.expiresAt <= new Date() ||
      !storedToken.user.isActive
    ) {
      throw new UnauthorizedException('Недействительный refresh token')
    }

    await this.prisma.refreshToken.update({
      where: { id: storedToken.id },
      data: { revokedAt: new Date() }
    })

    return this.issueSession(storedToken.user)
  }

  async logout(dto: RefreshDto) {
    if (!dto.refreshToken) {
      return { ok: true }
    }

    await this.prisma.refreshToken.updateMany({
      where: {
        tokenHash: this.hashToken(dto.refreshToken),
        revokedAt: null
      },
      data: { revokedAt: new Date() }
    })

    return { ok: true }
  }

  async getProfile(user: JwtUser) {
    const profile = await this.prisma.user.findUnique({
      where: { id: user.sub },
      select: {
        id: true,
        login: true,
        email: true,
        emailVerifiedAt: true,
        avatarUrl: true,
        role: true,
        isActive: true,
        createdAt: true
      }
    })

    if (!profile?.isActive) {
      throw new UnauthorizedException('Пользователь неактивен')
    }

    return profile
  }

  async requestEmailChange(user: JwtUser, dto: RequestEmailChangeDto) {
    const targetEmail = this.requireEmail(dto.email)
    const existingUser = await this.prisma.user.findUnique({ where: { email: targetEmail } })
    if (existingUser && existingUser.id !== user.sub) {
      throw new ConflictException('Пользователь с такой почтой уже существует')
    }

    const code = String(Math.floor(100000 + Math.random() * 900000))
    await this.prisma.emailVerificationCode.create({
      data: {
        userId: user.sub,
        targetEmail,
        codeHash: this.hashToken(code),
        purpose: EmailVerificationPurpose.EMAIL_CHANGE,
        expiresAt: new Date(Date.now() + EMAIL_CODE_TTL_MINUTES * 60 * 1000)
      }
    })

    await this.emailService.sendEmailChangeCode(targetEmail, code)

    return { ok: true }
  }

  async confirmEmailChange(user: JwtUser, dto: ConfirmEmailChangeDto) {
    const targetEmail = this.requireEmail(dto.email)
    const code = this.requireString(dto.code, 'Код подтверждения обязателен')
    const verification = await this.prisma.emailVerificationCode.findFirst({
      where: {
        userId: user.sub,
        targetEmail,
        purpose: EmailVerificationPurpose.EMAIL_CHANGE,
        codeHash: this.hashToken(code),
        usedAt: null,
        expiresAt: { gt: new Date() }
      },
      orderBy: { createdAt: 'desc' }
    })

    if (!verification) {
      throw new BadRequestException('Код подтверждения недействителен или истёк')
    }

    const updatedUser = await this.prisma.$transaction(async (tx) => {
      await tx.emailVerificationCode.update({
        where: { id: verification.id },
        data: { usedAt: new Date() }
      })

      return tx.user.update({
        where: { id: user.sub },
        data: {
          email: targetEmail,
          emailVerifiedAt: new Date()
        }
      })
    })

    return this.issueSession(updatedUser)
  }

  async changePassword(user: JwtUser, dto: ChangePasswordDto) {
    const currentPassword = this.requireString(dto.currentPassword, 'Текущий пароль обязателен')
    const newPassword = this.requirePassword(dto.newPassword)
    if (newPassword !== dto.confirmPassword) {
      throw new BadRequestException('Пароли не совпадают')
    }

    const currentUser = await this.prisma.user.findUnique({ where: { id: user.sub } })
    if (!currentUser?.passwordHash) {
      throw new BadRequestException('Для OAuth-профиля сначала задайте локальный пароль')
    }

    const isPasswordValid = await bcrypt.compare(currentPassword, currentUser.passwordHash)
    if (!isPasswordValid) {
      throw new UnauthorizedException('Текущий пароль указан неверно')
    }

    await this.prisma.user.update({
      where: { id: user.sub },
      data: { passwordHash: await bcrypt.hash(newPassword, 12) }
    })

    return { ok: true }
  }

  async uploadAvatar(user: JwtUser, file?: Express.Multer.File) {
    if (!file) {
      throw new BadRequestException('Файл аватара обязателен')
    }

    const currentUser = await this.prisma.user.findUnique({ where: { id: user.sub } })
    if (!currentUser?.isActive) {
      throw new UnauthorizedException('Пользователь неактивен')
    }

    const avatarUrl = await this.avatarStorageService.uploadAvatar(user.sub, file)
    await this.avatarStorageService.deleteByUrl(currentUser.avatarUrl)

    const updatedUser = await this.prisma.user.update({
      where: { id: user.sub },
      data: { avatarUrl }
    })

    return this.serializeUser(updatedUser)
  }

  async deleteAvatar(user: JwtUser) {
    const currentUser = await this.prisma.user.findUnique({ where: { id: user.sub } })
    if (!currentUser?.isActive) {
      throw new UnauthorizedException('Пользователь неактивен')
    }

    await this.avatarStorageService.deleteByUrl(currentUser.avatarUrl)
    const updatedUser = await this.prisma.user.update({
      where: { id: user.sub },
      data: { avatarUrl: null }
    })

    return this.serializeUser(updatedUser)
  }

  async promoteUser(currentUser: JwtUser, userId: string, dto: PromoteUserDto) {
    const role = dto.role ?? UserRole.ADMIN
    if (!Object.values(UserRole).includes(role)) {
      throw new BadRequestException('Некорректная роль')
    }

    const targetUser = await this.getModerationTarget(currentUser, userId, 'role')
    if (currentUser.role !== UserRole.SUPER_ADMIN && role !== UserRole.ANALYST) {
      throw new ForbiddenException('Администратор может только вернуть пользователя к обычной роли')
    }
    if (targetUser.id === currentUser.sub) {
      throw new ForbiddenException('Нельзя изменить собственную роль')
    }

    try {
      const updatedUser = await this.prisma.user.update({
        where: { id: userId },
        data: { role },
        select: {
          id: true,
          login: true,
          email: true,
          emailVerifiedAt: true,
          avatarUrl: true,
          role: true,
          isActive: true,
          createdAt: true,
          accounts: {
            select: {
              provider: true
            }
          }
        }
      })
      return this.withModerationPermissions(currentUser, updatedUser)
    } catch {
      throw new NotFoundException('Пользователь не найден')
    }
  }

  async listUsers(currentUser: JwtUser) {
    const users = await this.prisma.user.findMany({
      orderBy: { createdAt: 'desc' },
      take: 50,
      select: {
        id: true,
        login: true,
        email: true,
        emailVerifiedAt: true,
        avatarUrl: true,
        role: true,
        isActive: true,
        createdAt: true,
        accounts: {
          select: {
            provider: true
          }
        }
      }
    })

    return Promise.all(users.map((user) => this.withModerationPermissions(currentUser, user)))
  }

  async banUser(currentUser: JwtUser, userId: string) {
    await this.getModerationTarget(currentUser, userId, 'ban')
    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: { isActive: false },
      select: this.adminUserSelect()
    })

    await this.prisma.refreshToken.updateMany({
      where: { userId, revokedAt: null },
      data: { revokedAt: new Date() }
    })

    return this.withModerationPermissions(currentUser, updatedUser)
  }

  async unbanUser(currentUser: JwtUser, userId: string) {
    await this.getModerationTarget(currentUser, userId, 'unban')
    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: { isActive: true },
      select: this.adminUserSelect()
    })

    return this.withModerationPermissions(currentUser, updatedUser)
  }

  async deleteUser(currentUser: JwtUser, userId: string) {
    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      throw new ForbiddenException('Удаление доступно только главному администратору')
    }
    if (currentUser.sub === userId) {
      throw new ForbiddenException('Нельзя удалить собственный аккаунт')
    }

    const targetUser = await this.prisma.user.findUnique({ where: { id: userId } })
    if (!targetUser) {
      throw new NotFoundException('Пользователь не найден')
    }

    await this.avatarStorageService.deleteByUrl(targetUser.avatarUrl)
    await this.prisma.$transaction(async (tx) => {
      await tx.adminInvite.deleteMany({
        where: {
          OR: [
            { createdBy: userId },
            { usedBy: userId }
          ]
        }
      })
      await tx.user.delete({ where: { id: userId } })
    })

    return { ok: true }
  }

  private adminUserSelect() {
    return {
      id: true,
      login: true,
      email: true,
      emailVerifiedAt: true,
      avatarUrl: true,
      role: true,
      isActive: true,
      createdAt: true,
      accounts: {
        select: {
          provider: true
        }
      }
    } as const
  }

  private async getModerationTarget(
    currentUser: JwtUser,
    targetUserId: string,
    action: 'role' | 'ban' | 'unban'
  ) {
    if (currentUser.sub === targetUserId) {
      throw new ForbiddenException('Нельзя модерировать собственный аккаунт')
    }

    const targetUser = await this.prisma.user.findUnique({ where: { id: targetUserId } })
    if (!targetUser) {
      throw new NotFoundException('Пользователь не найден')
    }

    if (currentUser.role === UserRole.SUPER_ADMIN) {
      return targetUser
    }

    if (targetUser.role !== UserRole.ANALYST) {
      throw new ForbiddenException('Администратор может модерировать только обычных пользователей')
    }

    const usedInvite = await this.prisma.adminInvite.findFirst({
      where: { usedBy: currentUser.sub },
      select: { createdBy: true }
    })

    if (usedInvite?.createdBy === targetUserId) {
      throw new ForbiddenException('Нельзя модерировать администратора, который выдал приглашение')
    }

    if (action === 'role') {
      return targetUser
    }

    return targetUser
  }

  private async withModerationPermissions<T extends {
    id: string
    role: UserRole
    isActive: boolean
  }>(currentUser: JwtUser, user: T) {
    if (currentUser.role === UserRole.SUPER_ADMIN) {
      return {
        ...user,
        canChangeRole: currentUser.sub !== user.id,
        canBan: currentUser.sub !== user.id && user.isActive,
        canUnban: currentUser.sub !== user.id && !user.isActive,
        canDelete: currentUser.sub !== user.id
      }
    }

    const usedInvite = await this.prisma.adminInvite.findFirst({
      where: { usedBy: currentUser.sub },
      select: { createdBy: true }
    })
    const canModerate = currentUser.sub !== user.id &&
      user.role === UserRole.ANALYST &&
      usedInvite?.createdBy !== user.id

    return {
      ...user,
      canChangeRole: canModerate,
      canBan: canModerate && user.isActive,
      canUnban: canModerate && !user.isActive,
      canDelete: false
    }
  }

  async createInvite(currentUser: JwtUser, dto: CreateInviteDto) {
    const expiresInHours = dto.expiresInHours ?? 24
    if (!Number.isInteger(expiresInHours) || expiresInHours < 1 || expiresInHours > 24 * 14) {
      throw new BadRequestException('Срок invite должен быть от 1 часа до 14 дней')
    }

    const role = UserRole.ADMIN

    const token = randomBytes(32).toString('base64url')
    const invite = await this.prisma.adminInvite.create({
      data: {
        tokenHash: this.hashToken(token),
        role,
        createdBy: currentUser.sub,
        expiresAt: new Date(Date.now() + expiresInHours * 60 * 60 * 1000)
      },
      select: {
        id: true,
        role: true,
        expiresAt: true,
        createdAt: true
      }
    })

    return {
      ...invite,
      token
    }
  }

  async startOAuth(providerParam: string) {
    const provider = this.parseOAuthProvider(providerParam)
    const config = this.getOAuthConfig(provider)
    const state = randomBytes(32).toString('base64url')

    await this.prisma.oAuthState.create({
      data: {
        provider,
        stateHash: this.hashToken(state),
        expiresAt: new Date(Date.now() + OAUTH_STATE_TTL_MINUTES * 60 * 1000)
      }
    })

    const url = new URL(config.authorizeUrl)
    url.searchParams.set('response_type', 'code')
    url.searchParams.set('client_id', config.clientId)
    url.searchParams.set('redirect_uri', config.redirectUri)
    url.searchParams.set('scope', config.scope)
    url.searchParams.set('state', state)

    if (provider === OAuthProvider.GOOGLE) {
      url.searchParams.set('access_type', 'offline')
      url.searchParams.set('prompt', 'select_account')
    }

    return url.toString()
  }

  async handleOAuthCallback(providerParam: string, code?: string, state?: string) {
    if (!code || !state) {
      throw new BadRequestException('OAuth callback должен содержать code и state')
    }

    const provider = this.parseOAuthProvider(providerParam)
    const oauthState = await this.prisma.oAuthState.findUnique({
      where: { stateHash: this.hashToken(state) }
    })

    if (
      !oauthState ||
      oauthState.provider !== provider ||
      oauthState.usedAt ||
      oauthState.expiresAt <= new Date()
    ) {
      throw new UnauthorizedException('Недействительное OAuth-состояние')
    }

    await this.prisma.oAuthState.update({
      where: { id: oauthState.id },
      data: { usedAt: new Date() }
    })

    const tokens = await this.exchangeOAuthCode(provider, code)
    const profile = await this.fetchOAuthProfile(provider, tokens.accessToken, tokens)
    const user = await this.findOrCreateOAuthUser(profile)

    return this.issueSession(user)
  }

  private async issueSession(user: User) {
    const payload: JwtUser = {
      sub: user.id,
      login: user.login,
      email: user.email,
      role: user.role
    }
    const accessToken = await this.jwtService.signAsync(payload, {
      secret: this.configService.get<string>('JWT_ACCESS_SECRET') ?? 'dev-access-secret',
      expiresIn: ACCESS_TTL_SECONDS
    })
    const refreshToken = randomBytes(48).toString('base64url')
    const expiresAt = new Date(Date.now() + REFRESH_TTL_DAYS * 24 * 60 * 60 * 1000)

    await this.prisma.refreshToken.create({
      data: {
        userId: user.id,
        tokenHash: this.hashToken(refreshToken),
        expiresAt
      }
    })

    return {
      accessToken,
      refreshToken,
      expiresIn: ACCESS_TTL_SECONDS,
      user: this.serializeUser(user)
    }
  }

  private async findOrCreateOAuthUser(profile: OAuthProfile) {
    const account = await this.prisma.authAccount.findUnique({
      where: {
        provider_providerAccountId: {
          provider: profile.provider,
          providerAccountId: profile.providerAccountId
        }
      },
      include: { user: true }
    })

    if (account?.user.isActive) {
      return account.user
    }

    const email = profile.email?.toLowerCase()
    const loginBase = this.toLoginBase(profile.login ?? email ?? `${profile.provider.toLowerCase()}_user`)

    return this.prisma.$transaction(async (tx) => {
      const existingUser = email
        ? await tx.user.findUnique({ where: { email } })
        : null
      const user = existingUser ?? await tx.user.create({
        data: {
          login: await this.getUniqueLogin(loginBase, async (candidate) => {
            const existing = await tx.user.findUnique({ where: { login: candidate } })
            return Boolean(existing)
          }),
          email: email ?? `${profile.provider.toLowerCase()}_${profile.providerAccountId}@oauth.local`,
          role: UserRole.ANALYST
        }
      })

      await tx.authAccount.create({
        data: {
          userId: user.id,
          provider: profile.provider,
          providerAccountId: profile.providerAccountId,
          email
        }
      })

      return user
    })
  }

  private async getUniqueLogin(base: string, exists?: (candidate: string) => Promise<boolean>) {
    const normalized = this.toLoginBase(base)
    let candidate = normalized
    let suffix = 1
    const isTaken = exists ?? (async (login: string) => {
      const existing = await this.prisma.user.findUnique({ where: { login } })
      return Boolean(existing)
    })

    while (await isTaken(candidate)) {
      suffix += 1
      candidate = `${normalized}_${suffix}`
    }

    return candidate
  }

  private toLoginBase(value: string) {
    const normalized = value
      .toLowerCase()
      .replace(/@.*$/, '')
      .replace(/[^a-z0-9_.-]/g, '_')
      .replace(/^[^a-z0-9_]+/, '')
      .slice(0, 40)

    return /^[a-z0-9_][a-z0-9_.-]{2,47}$/.test(normalized)
      ? normalized
      : `user_${randomBytes(4).toString('hex')}`
  }

  private getOAuthConfig(provider: OAuthProvider) {
    const backendUrl = this.configService.get<string>('BACKEND_PUBLIC_URL') ?? 'http://localhost:8000'
    const redirectUri = `${backendUrl}/api/auth/oauth/${provider.toLowerCase()}/callback`

    const configMap = {
      [OAuthProvider.GOOGLE]: {
        clientId: this.configService.get<string>('GOOGLE_CLIENT_ID'),
        clientSecret: this.configService.get<string>('GOOGLE_CLIENT_SECRET'),
        authorizeUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenUrl: 'https://oauth2.googleapis.com/token',
        userInfoUrl: 'https://openidconnect.googleapis.com/v1/userinfo',
        scope: 'openid email profile',
        redirectUri
      },
      [OAuthProvider.YANDEX]: {
        clientId: this.configService.get<string>('YANDEX_CLIENT_ID'),
        clientSecret: this.configService.get<string>('YANDEX_CLIENT_SECRET'),
        authorizeUrl: 'https://oauth.yandex.ru/authorize',
        tokenUrl: 'https://oauth.yandex.ru/token',
        userInfoUrl: 'https://login.yandex.ru/info?format=json',
        scope: 'login:email login:info',
        redirectUri
      },
      [OAuthProvider.VK]: {
        clientId: this.configService.get<string>('VK_CLIENT_ID'),
        clientSecret: this.configService.get<string>('VK_CLIENT_SECRET'),
        authorizeUrl: 'https://oauth.vk.com/authorize',
        tokenUrl: 'https://oauth.vk.com/access_token',
        userInfoUrl: 'https://api.vk.com/method/users.get',
        scope: 'email',
        redirectUri
      }
    } satisfies Record<OAuthProvider, {
      clientId?: string
      clientSecret?: string
      authorizeUrl: string
      tokenUrl: string
      userInfoUrl: string
      scope: string
      redirectUri: string
    }>

    const config = configMap[provider]
    if (!config.clientId || !config.clientSecret) {
      throw new BadRequestException(`OAuth ${provider} не настроен в env`)
    }

    return {
      ...config,
      clientId: config.clientId,
      clientSecret: config.clientSecret
    }
  }

  private async exchangeOAuthCode(provider: OAuthProvider, code: string) {
    const config = this.getOAuthConfig(provider)
    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      client_id: config.clientId,
      client_secret: config.clientSecret,
      redirect_uri: config.redirectUri
    })

    if (provider === OAuthProvider.VK) {
      body.set('v', '5.199')
    }

    const response = await axios.post(config.tokenUrl, body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })

    const accessToken = response.data?.access_token as string | undefined
    if (!accessToken) {
      throw new UnauthorizedException('OAuth provider не вернул access token')
    }

    return {
      accessToken,
      email: response.data?.email as string | undefined,
      userId: response.data?.user_id as number | string | undefined
    }
  }

  private async fetchOAuthProfile(
    provider: OAuthProvider,
    accessToken: string,
    tokenData?: { email?: string; userId?: number | string }
  ): Promise<OAuthProfile> {
    if (provider === OAuthProvider.GOOGLE) {
      const response = await axios.get('https://openidconnect.googleapis.com/v1/userinfo', {
        headers: { Authorization: `Bearer ${accessToken}` }
      })
      return {
        provider,
        providerAccountId: String(response.data.sub),
        email: response.data.email,
        login: response.data.email ?? response.data.name
      }
    }

    if (provider === OAuthProvider.YANDEX) {
      const response = await axios.get('https://login.yandex.ru/info?format=json', {
        headers: { Authorization: `OAuth ${accessToken}` }
      })
      return {
        provider,
        providerAccountId: String(response.data.id),
        email: response.data.default_email,
        login: response.data.login
      }
    }

    const response = await axios.get('https://api.vk.com/method/users.get', {
      params: {
        access_token: accessToken,
        fields: 'domain',
        v: '5.199'
      }
    })
    const user = response.data?.response?.[0]
    if (!user?.id) {
      throw new UnauthorizedException('VK не вернул профиль пользователя')
    }

    return {
      provider,
      providerAccountId: String(user.id),
      email: tokenData?.email,
      login: user.domain ?? `vk_${user.id}`
    }
  }

  private parseOAuthProvider(provider: string) {
    const normalized = provider.toUpperCase()
    if (!Object.values(OAuthProvider).includes(normalized as OAuthProvider)) {
      throw new BadRequestException('Неподдерживаемый OAuth provider')
    }

    return normalized as OAuthProvider
  }

  private serializeUser(user: User) {
    return {
      id: user.id,
      login: user.login,
      email: user.email,
      emailVerifiedAt: user.emailVerifiedAt,
      avatarUrl: user.avatarUrl,
      role: user.role,
      isActive: user.isActive,
      createdAt: user.createdAt
    }
  }

  private async getActiveInvite(token: string) {
    const invite = await this.prisma.adminInvite.findUnique({
      where: { tokenHash: this.hashToken(token) }
    })

    if (!invite || invite.usedAt || invite.expiresAt <= new Date()) {
      throw new ForbiddenException('Invite-link недействителен или уже использован')
    }

    return invite
  }

  private hashToken(token: string) {
    return createHash('sha256').update(token).digest('hex')
  }

  private requireLogin(value: unknown) {
    const login = this.requireString(value, 'Логин обязателен').toLowerCase()
    if (!/^[a-z0-9_][a-z0-9_.-]{2,47}$/.test(login)) {
      throw new BadRequestException('Логин должен быть 3-48 символов: латиница, цифры, _, . или -')
    }
    return login
  }

  private requireEmail(value: unknown) {
    const email = this.requireString(value, 'Почта обязательна').toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
      throw new BadRequestException('Некорректная почта')
    }
    return email
  }

  private requirePassword(value: unknown) {
    const password = this.requireString(value, 'Пароль обязателен')
    if (password.length < 8 || password.length > 128) {
      throw new BadRequestException('Пароль должен быть от 8 до 128 символов')
    }
    return password
  }

  private requireString(value: unknown, message: string) {
    if (typeof value !== 'string' || value.trim().length === 0) {
      throw new BadRequestException(message)
    }

    return value.trim()
  }
}
