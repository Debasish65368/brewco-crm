import { AlertCircle, RefreshCw } from "lucide-react";

function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-red-900 shadow-sm">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{title}</h2>
          {message && <p className="mt-1 text-sm leading-6 text-red-800">{message}</p>}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-md bg-red-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-400"
            >
              <RefreshCw size={15} />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ErrorState;