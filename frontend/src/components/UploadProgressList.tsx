import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export interface UploadTask {
  id: number;
  name: string;
  progress: number; // 0..1
  state: "uploading" | "done" | "error";
  message?: string;
}

export function UploadProgressList({ tasks }: { tasks: UploadTask[] }) {
  if (tasks.length === 0) return null;
  return (
    <ul aria-label="Uploads" className="grid gap-2">
      {tasks.map((task) => (
        <li key={task.id} className="rounded-lg border bg-card p-3 text-sm">
          <div className="flex items-center gap-2">
            {task.state === "uploading" ? (
              <Loader2 className="size-4 animate-spin text-info" aria-hidden="true" />
            ) : task.state === "done" ? (
              <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
            ) : (
              <AlertCircle className="size-4 text-destructive" aria-hidden="true" />
            )}
            <span className="min-w-0 flex-1 truncate font-medium">{task.name}</span>
            <span className="text-xs text-muted-foreground">
              {task.state === "uploading" ? `${Math.round(task.progress * 100)}%` : task.message}
            </span>
          </div>
          {task.state === "uploading" ? (
            <progress
              value={task.progress}
              max={1}
              aria-label={`Uploading ${task.name}`}
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full [&::-moz-progress-bar]:bg-ring [&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:bg-ring"
            />
          ) : null}
          {task.state === "error" ? (
            <p role="alert" className="mt-1 text-destructive">
              {task.message}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
