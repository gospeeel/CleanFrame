import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException
} from '@nestjs/common'
import { JwtService } from '@nestjs/jwt'
import { ConfigService } from '@nestjs/config'
import { AuthRequest, JwtUser } from './auth.types'

@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService
  ) {}

  async canActivate(context: ExecutionContext) {
    const request = context.switchToHttp().getRequest<AuthRequest>()
    const token = this.extractToken(request)

    if (!token) {
      throw new UnauthorizedException('Требуется авторизация')
    }

    try {
      request.user = await this.jwtService.verifyAsync<JwtUser>(token, {
        secret: this.configService.get<string>('JWT_ACCESS_SECRET') ?? 'dev-access-secret'
      })
      return true
    } catch {
      throw new UnauthorizedException('Недействительный access token')
    }
  }

  private extractToken(request: AuthRequest) {
    const authorization = request.headers?.authorization
    if (!authorization) {
      return null
    }

    const [type, token] = authorization.split(' ')
    return type === 'Bearer' ? token : null
  }
}
