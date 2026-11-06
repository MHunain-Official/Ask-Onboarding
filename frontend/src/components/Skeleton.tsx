// Simple loading placeholder. Announces "Loading" to screen readers once.
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-2">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className="h-4 animate-pulse rounded bg-muted motion-reduce:animate-none"
          style={{
            width: `${index === lines - 1 ? 60 : 100 - ((index * 7) % 25)}%`,
          }}
        />
      ))}
    </div>
  );
}
