"use client";

import type { ReactNode } from "react";
import { isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { MermaidDiagram } from "@/components/admin/MermaidDiagram";
import { isExternalHref, resolveInternalDocPath } from "@/lib/docLinks";

function codeText(children: ReactNode): string {
  return String(children ?? "").replace(/\n$/, "");
}

interface DocMarkdownProps {
  text: string;
  /** Catalogue path of the open file, used to resolve relative links. */
  currentPath: string;
  /** Known allowlisted paths from `/api/admin/project-docs`. */
  knownPaths: Set<string>;
  onOpenDoc: (path: string) => void;
}

/** Safe markdown for project docs: GFM tables, Mermaid, in-app doc links. */
export function DocMarkdown({ text, currentPath, knownPaths, onOpenDoc }: DocMarkdownProps) {
  return (
    <div className="doc-prose font-sans text-[0.95rem] leading-7 text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="font-heading mt-10 mb-3 text-3xl font-semibold tracking-tight first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-heading mt-10 mb-3 border-b border-border/60 pb-2 text-xl font-semibold tracking-tight">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="font-heading mt-7 mb-2 text-lg font-semibold">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-5 mb-1.5 text-base font-semibold">{children}</h4>
          ),
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-4 list-disc space-y-1.5 pl-5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 list-decimal space-y-1.5 pl-5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <DocLink
              href={href}
              currentPath={currentPath}
              knownPaths={knownPaths}
              onOpenDoc={onOpenDoc}
            >
              {children}
            </DocLink>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-4 border-l-2 border-ring/50 pl-4 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) => {
            const language = /language-([a-z0-9+-]+)/i.exec(className ?? "")?.[1];
            if (language === "mermaid") {
              return <MermaidDiagram chart={codeText(children)} />;
            }
            if (language || codeText(children).includes("\n")) {
              return (
                <code className="font-mono text-[0.85em] whitespace-pre-wrap">{children}</code>
              );
            }
            return (
              <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">
                {children}
              </code>
            );
          },
          pre: ({ children }) => {
            if (isValidElement(children) && "chart" in (children.props as object)) {
              return children;
            }
            return (
              <pre className="mb-5 overflow-x-auto rounded-2xl border border-border/60 bg-muted/60 p-4 font-mono text-sm leading-relaxed">
                {children}
              </pre>
            );
          },
          table: ({ children }) => (
            <div className="mb-5 overflow-x-auto rounded-2xl border border-border/70 shadow-sm">
              <table className="w-full min-w-[28rem] border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-muted/80">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => (
            <tr className="odd:bg-card/40 even:bg-muted/20">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="border-b border-border/80 px-3 py-2.5 text-left align-top font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-border/50 px-3 py-2.5 align-top leading-relaxed">
              {children}
            </td>
          ),
          hr: () => <hr className="my-8 border-border/70" />,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function DocLink({
  href,
  children,
  currentPath,
  knownPaths,
  onOpenDoc,
}: {
  href?: string;
  children: ReactNode;
  currentPath: string;
  knownPaths: Set<string>;
  onOpenDoc: (path: string) => void;
}) {
  const target = href ?? "";
  const internal = resolveInternalDocPath(currentPath, target);
  const linkClass = "font-medium text-ring underline underline-offset-2";

  if (internal && knownPaths.has(internal)) {
    return (
      <button
        type="button"
        onClick={() => onOpenDoc(internal)}
        className={`${linkClass} cursor-pointer text-left`}
      >
        {children}
      </button>
    );
  }

  if (internal && !knownPaths.has(internal)) {
    // Linked file is not in the catalogue — show path, don't pretend it works.
    return (
      <span className="font-medium text-muted-foreground underline decoration-dashed underline-offset-2">
        {children}
        <span className="ml-1 font-mono text-[0.7rem] no-underline">({internal})</span>
      </span>
    );
  }

  if (target.startsWith("#") || !target) {
    return <span className={linkClass}>{children}</span>;
  }

  return (
    <a
      href={target}
      target={isExternalHref(target) ? "_blank" : undefined}
      rel={isExternalHref(target) ? "noopener noreferrer" : undefined}
      className={linkClass}
    >
      {children}
    </a>
  );
}
