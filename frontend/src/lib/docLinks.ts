/** Resolve markdown hrefs to catalogue paths used by Admin → Docs. */

export function isExternalHref(href: string): boolean {
  return /^(https?:|mailto:|tel:)/i.test(href);
}

/**
 * Turn a relative markdown link into a project-doc path
 * (e.g. from `SECURITY.md` + `docs/threat-model.md` → `docs/threat-model.md`).
 * Returns null for external URLs, anchors-only, or empty targets.
 */
export function resolveInternalDocPath(currentPath: string, href: string): string | null {
  const raw = href.trim();
  if (!raw || raw.startsWith("#") || isExternalHref(raw)) return null;

  const withoutHash = raw.split("#")[0]?.split("?")[0] ?? "";
  if (!withoutHash) return null;

  const cleaned = withoutHash.replace(/^\.\//, "");
  if (cleaned.startsWith("/")) {
    return normalizePath(cleaned.slice(1));
  }

  const baseDir = currentPath.includes("/")
    ? currentPath.slice(0, currentPath.lastIndexOf("/"))
    : "";
  const joined = baseDir ? `${baseDir}/${cleaned}` : cleaned;
  return normalizePath(joined);
}

function normalizePath(path: string): string {
  const parts: string[] = [];
  for (const part of path.replace(/\\/g, "/").split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") {
      parts.pop();
      continue;
    }
    parts.push(part);
  }
  return parts.join("/");
}
