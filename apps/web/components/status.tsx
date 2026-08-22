import { AlertIcon } from "@/components/icons";

export function LoadingLine({ label = "Sto preparando lo spazio…" }: { label?: string }) {
  return (
    <div className="loading-line" role="status">
      <span className="loading-line__mark" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function InlineError({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="inline-error" role="alert">
      <AlertIcon />
      <span>{message}</span>
      {retry && <button type="button" onClick={retry}>Riprova</button>}
    </div>
  );
}
