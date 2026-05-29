export function normalizeUploadFileName(fileName: string) {
  if (!fileName) {
    return fileName
  }

  try {
    const decoded = Buffer.from(fileName, 'latin1').toString('utf8')
    return decoded.includes('�') ? fileName : decoded
  } catch {
    return fileName
  }
}
