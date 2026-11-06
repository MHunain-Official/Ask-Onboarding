// Client-side upload checks. They only make the UI friendlier: the server
// re-checks extension, magic bytes and size, and is the real gatekeeper (§3.2).

export const ALLOWED_EXTENSIONS = [".pdf", ".md", ".txt"];
export const MAX_UPLOAD_MB = 10; // keep in sync with MAX_UPLOAD_MB in .env

export function checkUploadFile(file: { name: string; size: number }): string | null {
  const lowerName = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))) {
    return `${file.name}: only PDF, Markdown and text files are supported.`;
  }
  if (file.size === 0) return `${file.name}: the file is empty.`;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `${file.name}: larger than ${MAX_UPLOAD_MB} MB.`;
  }
  return null;
}
