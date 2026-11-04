/**
 * Multipart body for `POST /api/session/{id}/document`.
 * The API reads the image from the field named `file` (api/listen/routes.py
 * `upload_document(file: UploadFile = File(...), document_id: str | None = Form())`).
 * Pure module (no React / Next imports) so `tests/` can run it with `node --test`.
 */
export const DOCUMENT_FIELD = "file"
export const DOCUMENT_ID_FIELD = "document_id"

export function documentForm(image: Blob, name: string, documentId?: string): FormData {
  const form = new FormData()
  form.append(DOCUMENT_FIELD, image, name)
  if (documentId) form.append(DOCUMENT_ID_FIELD, documentId)
  return form
}
