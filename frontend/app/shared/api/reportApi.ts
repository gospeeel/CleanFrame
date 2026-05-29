export interface Recommendation {
  id: number
  text: string
  severity: 'low' | 'medium' | 'high'
}

export interface ReportData {
  ageRating: number
  recommendations: Recommendation[]
  criticalPoints: { scene: string; score: number }[]
}

export async function fetchReport(): Promise<ReportData> {
  return {
    ageRating: 12,
    recommendations: [
      { id: 1, text: 'Уменьшите количество сцен с насилием', severity: 'high' },
      { id: 2, text: 'Замените грубый язык на более мягкий', severity: 'medium' },
      { id: 3, text: 'Добавьте предупреждения перед откровенными сценами', severity: 'low' }
    ],
    criticalPoints: [
      { scene: 'Сцена 5', score: 8 },
      { scene: 'Сцена 12', score: 9 }
    ]
  }
}
