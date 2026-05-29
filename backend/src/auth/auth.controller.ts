import { Body, Controller, Delete, Get, Param, Patch, Post, Query, Redirect, UploadedFile, UseGuards, UseInterceptors } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import { FileInterceptor } from '@nestjs/platform-express'
import { UserRole } from '@prisma/client'
import { AuthService } from './auth.service'
import { CurrentUser } from './current-user.decorator'
import { JwtAuthGuard } from './jwt-auth.guard'
import { Roles } from './roles.decorator'
import { RolesGuard } from './roles.guard'
import {
  CreateInviteDto,
  ChangePasswordDto,
  JwtUser,
  LoginDto,
  PromoteUserDto,
  RefreshDto,
  RegisterDto
} from './auth.types'

@Controller('api/auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly configService: ConfigService
  ) {}

  @Post('register')
  register(@Body() dto: RegisterDto) {
    return this.authService.register(dto)
  }

  @Post('login')
  login(@Body() dto: LoginDto) {
    return this.authService.login(dto)
  }

  @Post('refresh')
  refresh(@Body() dto: RefreshDto) {
    return this.authService.refresh(dto)
  }

  @Post('logout')
  logout(@Body() dto: RefreshDto) {
    return this.authService.logout(dto)
  }

  @Get('me')
  @UseGuards(JwtAuthGuard)
  me(@CurrentUser() user: JwtUser) {
    return this.authService.getProfile(user)
  }

  @Patch('profile/password')
  @UseGuards(JwtAuthGuard)
  changePassword(@CurrentUser() user: JwtUser, @Body() dto: ChangePasswordDto) {
    return this.authService.changePassword(user, dto)
  }

  @Post('profile/avatar')
  @UseGuards(JwtAuthGuard)
  @UseInterceptors(FileInterceptor('avatar'))
  uploadAvatar(@CurrentUser() user: JwtUser, @UploadedFile() file?: Express.Multer.File) {
    return this.authService.uploadAvatar(user, file)
  }

  @Delete('profile/avatar')
  @UseGuards(JwtAuthGuard)
  deleteAvatar(@CurrentUser() user: JwtUser) {
    return this.authService.deleteAvatar(user)
  }

  @Post('admin/invites')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  createInvite(@CurrentUser() user: JwtUser, @Body() dto: CreateInviteDto) {
    return this.authService.createInvite(user, dto)
  }

  @Get('admin/users')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  listUsers(@CurrentUser() user: JwtUser) {
    return this.authService.listUsers(user)
  }

  @Patch('admin/users/:id/role')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  promoteUser(@CurrentUser() user: JwtUser, @Param('id') userId: string, @Body() dto: PromoteUserDto) {
    return this.authService.promoteUser(user, userId, dto)
  }

  @Patch('admin/users/:id/ban')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  banUser(@CurrentUser() user: JwtUser, @Param('id') userId: string) {
    return this.authService.banUser(user, userId)
  }

  @Patch('admin/users/:id/unban')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  unbanUser(@CurrentUser() user: JwtUser, @Param('id') userId: string) {
    return this.authService.unbanUser(user, userId)
  }

  @Delete('admin/users/:id')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.SUPER_ADMIN)
  deleteUser(@CurrentUser() user: JwtUser, @Param('id') userId: string) {
    return this.authService.deleteUser(user, userId)
  }

  @Get('oauth/:provider')
  @Redirect()
  async oauthStart(@Param('provider') provider: string) {
    return {
      url: await this.authService.startOAuth(provider)
    }
  }

  @Get('oauth/:provider/callback')
  @Redirect()
  async oauthCallback(
    @Param('provider') provider: string,
    @Query('code') code?: string,
    @Query('state') state?: string
  ) {
    const session = await this.authService.handleOAuthCallback(provider, code, state)
    const frontendUrl = this.configService.get<string>('FRONTEND_URL') ?? 'http://localhost:3000'
    const payload = Buffer.from(JSON.stringify(session), 'utf8').toString('base64url')

    return {
      url: `${frontendUrl}/oauth/callback#session=${payload}`
    }
  }
}
