import { useState } from "react";
import { toast } from "sonner";
import { Bot, Layers3, Plus, Sparkles, Users } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import ErrorState from "@/components/common/ErrorState";
import LoadingSkeleton from "@/components/common/LoadingSkeleton";
import PageHeader from "@/layout/PageHeader";
import { useSegments } from "@/hooks/useSegments";
import { suggestSegment } from "@/services/aiApi";

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(value));
}

function Field({ label, children }) {
  return (
    <label className="block text-sm font-medium text-brew-brown">
      {label}
      <div className="mt-2">{children}</div>
    </label>
  );
}

function SegmentsPage() {
  const { data, loading, error, refetch, createSegment } = useSegments();
  const [form, setForm] = useState({ name: "", description: "" });
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiSuggestion, setAiSuggestion] = useState(null);
  const [creating, setCreating] = useState(false);
  const [suggesting, setSuggesting] = useState(false);

  const updateForm = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleCreateSegment = async (event) => {
    event.preventDefault();

    if (!form.name.trim()) {
      toast.error("Segment name is required");
      return;
    }

    setCreating(true);

    try {
      await createSegment({
        name: form.name.trim(),
        description: form.description.trim(),
        filter_json: aiSuggestion?.filter_json || {}
      });
      setForm({ name: "", description: "" });
      toast.success("Segment created successfully");
    } catch {
      toast.error("Failed to create segment");
    } finally {
      setCreating(false);
    }
  };

  const handleSuggestSegment = async () => {
    if (!aiPrompt.trim()) {
      toast.error("Enter a segment prompt first");
      return;
    }

    setSuggesting(true);

    try {
      const result = await suggestSegment(aiPrompt.trim());
      setAiSuggestion(result);
      toast.success("Segment suggestion ready");
    } catch {
      toast.error("Failed to suggest segment");
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Segments" description="Create and review customer groups for BrewCo campaigns." />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
        <div className="space-y-4">
          {loading ? (
            <LoadingSkeleton rows={4} />
          ) : error ? (
            <ErrorState message={error} onRetry={refetch} />
          ) : !data.length ? (
            <EmptyState
              icon={Layers3}
              title="No segments yet"
              description="Create a segment to group customers for targeted campaigns."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {data.map((segment) => (
                <article
                  key={segment.id}
                  className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-base font-semibold text-brew-brown">{segment.name}</h2>
                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-brew-roast">
                        {segment.description || "No description provided."}
                      </p>
                    </div>
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brew-amber/15 text-brew-amber">
                      <Users size={19} />
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2 text-xs text-brew-roast">
                    {typeof segment.customer_count === "number" && (
                      <span className="rounded-full bg-brew-cream px-2.5 py-1 ring-1 ring-brew-brown/10">
                        {segment.customer_count.toLocaleString("en-US")} customers
                      </span>
                    )}
                    {segment.created_at && (
                      <span className="rounded-full bg-brew-cream px-2.5 py-1 ring-1 ring-brew-brown/10">
                        Created {formatDate(segment.created_at)}
                      </span>
                    )}
                    {segment.id && (
                      <span className="rounded-full bg-brew-cream px-2.5 py-1 ring-1 ring-brew-brown/10">
                        ID {segment.id}
                      </span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-5">
          <form onSubmit={handleCreateSegment} className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-brew-brown">
              <Plus size={18} />
              Create Segment
            </div>
            <div className="mt-4 space-y-4">
              <Field label="Name">
                <input
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                  className="h-11 w-full rounded-md border border-brew-brown/15 bg-white px-3 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                  placeholder="High value customers"
                />
              </Field>
              <Field label="Description">
                <textarea
                  value={form.description}
                  onChange={(event) => updateForm("description", event.target.value)}
                  className="min-h-24 w-full rounded-md border border-brew-brown/15 bg-white px-3 py-2 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                  placeholder="Customers who should receive a premium roast offer"
                />
              </Field>
              <button
                type="submit"
                disabled={creating}
                className="inline-flex h-11 items-center justify-center rounded-md bg-brew-brown px-4 text-sm font-medium text-brew-foam transition hover:bg-brew-espresso disabled:cursor-not-allowed disabled:opacity-60"
              >
                {creating ? "Creating..." : "Create Segment"}
              </button>
            </div>
          </form>

          <section className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-brew-brown">
              <Bot size={18} />
              AI Segment Assistant
            </div>
            <div className="mt-4 space-y-4">
              <textarea
                value={aiPrompt}
                onChange={(event) => setAiPrompt(event.target.value)}
                className="min-h-28 w-full rounded-md border border-brew-brown/15 bg-white px-3 py-2 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                placeholder="Suggest a segment for customers in Mumbai who spent more than 5000"
              />
              <button
                type="button"
                onClick={handleSuggestSegment}
                disabled={suggesting}
                className="inline-flex h-11 items-center gap-2 rounded-md bg-brew-amber px-4 text-sm font-medium text-white transition hover:bg-brew-roast disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Sparkles size={16} />
                {suggesting ? "Suggesting..." : "Suggest Segment"}
              </button>

              {aiSuggestion && (
                <div className="rounded-lg border border-brew-amber/25 bg-brew-cream p-4">
                  <p className="text-sm font-semibold text-brew-brown">AI suggestion</p>
                  <pre className="mt-3 max-h-52 overflow-auto rounded-md bg-white p-3 text-xs text-brew-roast ring-1 ring-brew-brown/10">
                    {JSON.stringify(aiSuggestion.filter_json || aiSuggestion, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

export default SegmentsPage;