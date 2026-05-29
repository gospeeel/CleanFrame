import 'dotenv/config'
import { defineConfig } from 'prisma/config'

export default defineConfig({
  schema: 'prisma/schema.prisma',
  datasource: {
    url:
      process.env.DATABASE_URL ??
      'postgresql://ml_wink:ml_wink_password@localhost:5432/ml_wink?schema=public',
    shadowDatabaseUrl: process.env.SHADOW_DATABASE_URL
  },
  migrations: {
    path: 'prisma/migrations'
  }
})
