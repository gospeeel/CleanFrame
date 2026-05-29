import { SetMetadata } from '@nestjs/common'
import { UserRole } from '@prisma/client'

export const ROLES_KEY = 'roles'

export function Roles(...roles: UserRole[]) {
  return SetMetadata(ROLES_KEY, roles)
}
