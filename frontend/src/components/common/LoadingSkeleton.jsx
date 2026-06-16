function LoadingSkeleton({ rows = 3, className = "", variant = "block" }) {
  if (variant === "cards") {
    return (
      <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-4 ${className}`}>
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm">
            <div className="h-4 w-24 animate-pulse rounded bg-brew-brown/10" />
            <div className="mt-5 h-8 w-32 animate-pulse rounded bg-brew-brown/10" />
            <div className="mt-4 h-3 w-20 animate-pulse rounded bg-brew-brown/10" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-lg border border-brew-brown/10 bg-brew-foam p-4 shadow-sm">
          <div className="h-4 w-1/3 animate-pulse rounded bg-brew-brown/10" />
          <div className="mt-3 h-3 w-full animate-pulse rounded bg-brew-brown/10" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-brew-brown/10" />
        </div>
      ))}
    </div>
  );
}

export default LoadingSkeleton;