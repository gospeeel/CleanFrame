import 'dotenv/config'
import { PrismaPg } from '@prisma/adapter-pg'
import { PrismaClient, UserRole } from '@prisma/client'
import * as bcrypt from 'bcryptjs'

const connectionString = process.env.DATABASE_URL
if (!connectionString) {
  throw new Error('DATABASE_URL is required')
}

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString })
})

function requireEnv(name: string) {
  const value = process.env[name]
  if (!value) {
    throw new Error(`${name} is required`)
  }
  return value
}

function normalizeLogin(value: string) {
  return value.trim().toLowerCase()
}

function normalizeEmail(value: string) {
  return value.trim().toLowerCase()
}

async function main() {
  const login = normalizeLogin(requireEnv('SEED_ADMIN_LOGIN'))
  const email = normalizeEmail(requireEnv('SEED_ADMIN_EMAIL'))
  const password = requireEnv('SEED_ADMIN_PASSWORD')

  if (password.length < 8) {
    throw new Error('SEED_ADMIN_PASSWORD must be at least 8 characters')
  }

  const passwordHash = await bcrypt.hash(password, 12)
  const user = await prisma.user.upsert({
    where: { email },
    update: {
      login,
      passwordHash,
      role: UserRole.SUPER_ADMIN,
      isActive: true
    },
    create: {
      login,
      email,
      passwordHash,
      role: UserRole.SUPER_ADMIN,
      isActive: true
    }
  })

  console.log(`Super admin ready: ${user.email} (${user.id})`)
}

main()
  .catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
