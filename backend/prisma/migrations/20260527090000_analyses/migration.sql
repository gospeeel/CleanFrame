CREATE TYPE "AnalysisStatus" AS ENUM ('QUEUED', 'PROCESSING', 'DONE', 'FAILED');

CREATE TABLE "analyses" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "file_name" VARCHAR(255) NOT NULL,
    "status" "AnalysisStatus" NOT NULL DEFAULT 'QUEUED',
    "max_rating" VARCHAR(8),
    "risk_count" INTEGER NOT NULL DEFAULT 0,
    "review_count" INTEGER NOT NULL DEFAULT 0,
    "processing_time" DOUBLE PRECISION,
    "result_json" JSONB,
    "error_message" TEXT,
    "completed_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "analyses_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "analyses_user_id_created_at_idx" ON "analyses"("user_id", "created_at");
CREATE INDEX "analyses_status_idx" ON "analyses"("status");

ALTER TABLE "analyses" ADD CONSTRAINT "analyses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
