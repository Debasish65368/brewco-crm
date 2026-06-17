import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Bot, Loader2, Megaphone, PenLine, Send, Trash2 } from "lucide-react";
import Drawer from "@/components/common/Drawer";
import EmptyState from "@/components/common/EmptyState";
import ErrorState from "@/components/common/ErrorState";
import LoadingSkeleton from "@/components/common/LoadingSkeleton";
import StatusBadge from "@/components/common/StatusBadge";
import PageHeader from "@/layout/PageHeader";
import { useCampaigns } from "@/hooks/useCampaigns";
import { useSegments } from "@/hooks/useSegments";
import { draftMessage } from "@/services/aiApi";
import apiClient from "@/services/apiClient";

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(new Date(value));
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function getDeliveryRate(stats) {
  const sent = Number(stats?.sent || 0);
  const delivered = Number(stats?.delivered || 0);

  if (!sent) {
    return 0;
  }

  return Math.round((delivered / sent) * 1000) / 10;
}

function Field({ label, children }) {
  return (
    <label className="block text-sm font-medium text-brew-brown">
      {label}
      <div className="mt-2">{children}</div>
    </label>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-lg border border-brew-brown/10 bg-brew-cream p-4">
      <p className="text-xs font-medium uppercase text-brew-roast">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-brew-brown">{value}</p>
    </div>
  );
}

function FunnelBar({ label, value, max }) {
  const width = max > 0 ? Math.max(3, Math.min(100, (Number(value || 0) / max) * 100)) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-brew-brown">{label}</span>
        <span className="text-brew-roast">{formatNumber(value)}</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-brew-brown/10">
        <div className="h-full rounded-full bg-brew-amber transition-all" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function CampaignsPage() {
  const { data, loading, error, refetch, createCampaign, deleteCampaign } = useCampaigns();
  const { data: segments, loading: segmentsLoading } = useSegments();
  const [form, setForm] = useState({ name: "", segment_id: "", channel: "email", message: "" });
  const [goal, setGoal] = useState("");
  const [creating, setCreating] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campaignStats, setCampaignStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const selectedSegment = useMemo(
    () => segments.find((segment) => String(segment.id) === String(form.segment_id)),
    [form.segment_id, segments]
  );

  const updateForm = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleCreateCampaign = async (event) => {
    event.preventDefault();

    if (!form.name.trim() || !form.segment_id || !form.message.trim()) {
      toast.error("Campaign name, segment, and message are required");
      return;
    }

    setCreating(true);

    try {
      await createCampaign({
        name: form.name.trim(),
        segment_id: Number(form.segment_id),
        channel: form.channel,
        message: form.message.trim()
      });
      setForm({ name: "", segment_id: "", channel: "email", message: "" });
      toast.success("Campaign created successfully");
    } catch {
      toast.error("Failed to create campaign");
    } finally {
      setCreating(false);
    }
  };

  const handleDraftMessage = async () => {
    if (!goal.trim()) {
      toast.error("Enter a campaign goal first");
      return;
    }

    setDrafting(true);

    try {
      const result = await draftMessage(goal.trim());
      updateForm("message", result.message || "");
      toast.success("Message drafted");
    } catch {
      toast.error("Failed to draft message");
    } finally {
      setDrafting(false);
    }
  };

  const handleCampaignClick = async (campaign) => {
    setSelectedCampaign(campaign);
    setCampaignStats(null);
    setStatsError(null);
    setStatsLoading(true);

    try {
      const response = await apiClient.get(`/campaigns/${campaign.id}/stats`);
      setCampaignStats(response.data);
    } catch {
      setStatsError("Failed to load campaign stats");
    } finally {
      setStatsLoading(false);
    }
  };

  const closeStatsDrawer = () => {
    setSelectedCampaign(null);
    setCampaignStats(null);
    setStatsError(null);
    setStatsLoading(false);
  };

  const handleDeleteCampaign = async (campaign) => {
    setDeletingId(campaign.id);

    try {
      await deleteCampaign(campaign.id);
      setConfirmDeleteId(null);
      if (String(selectedCampaign?.id) === String(campaign.id)) {
        closeStatsDrawer();
      }
      toast.success("Campaign deleted successfully");
    } catch (err) {
      toast.error(err.message || "Failed to delete campaign");
    } finally {
      setDeletingId(null);
    }
  };

  const sentCount = Number(campaignStats?.sent || 0);
  const deliveryRate = getDeliveryRate(campaignStats);

  return (
    <div className="space-y-6">
      <PageHeader title="Campaigns" description="Create campaign messages and track BrewCo campaign history." />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(320px,380px)]">
        <div className="space-y-4">
          {loading ? (
            <LoadingSkeleton rows={5} />
          ) : error ? (
            <ErrorState message={error} onRetry={refetch} />
          ) : !data.length ? (
            <EmptyState
              icon={Megaphone}
              title="No campaigns yet"
              description="Create a campaign to start reaching BrewCo customer segments."
            />
          ) : (
            <section className="overflow-hidden rounded-lg border border-brew-brown/10 bg-brew-foam shadow-sm">
              <div className="scroll-container overflow-x-hidden">
                <table className="w-full table-fixed divide-y divide-brew-brown/10 text-sm">
                  <colgroup>
                    <col className="w-[30%]" />
                    <col className="w-[21%]" />
                    <col className="w-[11%]" />
                    <col className="w-[11%]" />
                    <col className="w-[12%]" />
                    <col className="w-[15%]" />
                  </colgroup>
                  <thead className="bg-brew-cream text-left text-xs uppercase text-brew-roast">
                    <tr>
                      <th className="px-3 py-3 font-semibold">Name</th>
                      <th className="px-3 py-3 font-semibold">Segment</th>
                      <th className="px-3 py-3 font-semibold">Channel</th>
                      <th className="px-3 py-3 font-semibold">Status</th>
                      <th className="px-3 py-3 font-semibold">Created</th>
                      <th className="px-3 py-3 text-right font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-brew-brown/10">
                    {data.map((campaign) => {
                      const isConfirmingDelete = String(confirmDeleteId) === String(campaign.id);
                      const isDeleting = String(deletingId) === String(campaign.id);

                      return (
                        <tr
                          key={campaign.id}
                          onClick={() => handleCampaignClick(campaign)}
                          className="cursor-pointer transition hover:bg-brew-cream/70"
                        >
                          <td className="truncate px-3 py-4 font-medium text-brew-brown" title={campaign.name}>
                            {campaign.name}
                          </td>
                          <td
                            className="truncate px-3 py-4 text-brew-roast"
                            title={campaign.segment_name || String(campaign.segment_id || "Not available")}
                          >
                            {campaign.segment_name || campaign.segment_id || "Not available"}
                          </td>
                          <td className="truncate px-3 py-4 capitalize text-brew-roast">{campaign.channel}</td>
                          <td className="px-3 py-4">
                            <StatusBadge value={campaign.status} />
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-brew-roast">{formatDate(campaign.created_at)}</td>
                          <td className="px-2 py-4 text-right" onClick={(event) => event.stopPropagation()}>
                            {isConfirmingDelete ? (
                              <div className="ml-auto flex w-24 flex-col items-end gap-1 rounded-lg border border-red-200 bg-red-50 px-1.5 py-1.5 shadow-sm">
                                <span className="w-full text-center text-[11px] font-semibold leading-none text-red-800">Delete?</span>
                                <div className="flex items-center gap-1">
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteCampaign(campaign)}
                                    disabled={isDeleting}
                                    className="rounded-md bg-red-700 px-2 py-1 text-xs font-medium text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    {isDeleting ? "..." : "Yes"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setConfirmDeleteId(null)}
                                    disabled={isDeleting}
                                    className="rounded-md border border-brew-brown/15 bg-brew-foam px-2 py-1 text-xs font-medium text-brew-brown transition hover:bg-brew-cream disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    No
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => setConfirmDeleteId(campaign.id)}
                                className="inline-grid h-9 w-9 place-items-center rounded-md text-brew-roast transition hover:bg-red-50 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-red-200"
                                aria-label={`Delete ${campaign.name}`}
                              >
                                <Trash2 size={17} />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>

        <div className="space-y-5">
          <form onSubmit={handleCreateCampaign} className="rounded-lg border border-brew-brown/10 bg-brew-foam p-4 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-brew-brown">
              <Send size={18} />
              Create Campaign
            </div>
            <div className="mt-3 space-y-3">
              <Field label="Campaign Name">
                <input
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                  className="h-10 w-full rounded-md border border-brew-brown/15 bg-white px-3 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                  placeholder="Weekend espresso offer"
                />
              </Field>

              <Field label="Segment">
                <select
                  value={form.segment_id}
                  onChange={(event) => updateForm("segment_id", event.target.value)}
                  disabled={segmentsLoading}
                  className="h-10 w-full rounded-md border border-brew-brown/15 bg-white px-3 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="">Select a segment</option>
                  {segments.map((segment) => (
                    <option key={segment.id} value={segment.id}>
                      {segment.name}
                    </option>
                  ))}
                </select>
              </Field>

              {selectedSegment && (
                <div className="rounded-lg border border-brew-amber/25 bg-brew-cream px-3 py-2 text-sm font-medium text-brew-roast">
                  {Number(selectedSegment.customer_count || 0) === 0
                    ? "⚠️ This segment has no customers"
                    : `📢 ${Number(selectedSegment.customer_count || 0).toLocaleString("en-US")} customers will receive this campaign`}
                </div>
              )}

              <Field label="Channel">
                <select
                  value={form.channel}
                  onChange={(event) => updateForm("channel", event.target.value)}
                  className="h-10 w-full rounded-md border border-brew-brown/15 bg-white px-3 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                >
                  <option value="email">Email</option>
                  <option value="sms">SMS</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </Field>

              <Field label="Message">
                <textarea
                  value={form.message}
                  onChange={(event) => updateForm("message", event.target.value)}
                  className="min-h-28 w-full rounded-md border border-brew-brown/15 bg-white px-3 py-2 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                  placeholder="Write a campaign message or draft one with AI."
                />
              </Field>

              <button
                type="submit"
                disabled={creating}
                className="inline-flex h-10 items-center justify-center rounded-md bg-brew-brown px-4 text-sm font-medium text-brew-foam transition hover:bg-brew-espresso disabled:cursor-not-allowed disabled:opacity-60"
              >
                {creating ? "Creating..." : "Create Campaign"}
              </button>
            </div>
          </form>

          <section className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-brew-brown">
              <Bot size={18} />
              AI Message Draft
            </div>
            <div className="mt-4 space-y-4">
              <Field label="Campaign Goal">
                <input
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  className="h-11 w-full rounded-md border border-brew-brown/15 bg-white px-3 text-sm text-brew-brown outline-none transition focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
                  placeholder="Bring back inactive customers with a cold brew offer"
                />
              </Field>
              <button
                type="button"
                onClick={handleDraftMessage}
                disabled={drafting}
                className="inline-flex h-11 items-center gap-2 rounded-md bg-brew-amber px-4 text-sm font-medium text-white transition hover:bg-brew-roast disabled:cursor-not-allowed disabled:opacity-60"
              >
                <PenLine size={16} />
                {drafting ? "Drafting..." : "Draft Message"}
              </button>
            </div>
          </section>
        </div>
      </section>

      <Drawer
        open={Boolean(selectedCampaign)}
        title={selectedCampaign?.name || "Campaign stats"}
        description={selectedCampaign ? `${selectedCampaign.segment_name || selectedCampaign.segment_id || "Segment unavailable"} · ${selectedCampaign.channel}` : ""}
        onClose={closeStatsDrawer}
      >
        {statsLoading ? (
          <div className="flex min-h-64 items-center justify-center rounded-lg border border-brew-brown/10 bg-brew-cream">
            <div className="flex items-center gap-3 text-sm font-medium text-brew-roast">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading campaign stats...
            </div>
          </div>
        ) : statsError ? (
          <ErrorState message={statsError} />
        ) : campaignStats ? (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <StatCard label="Sent" value={formatNumber(campaignStats.sent)} />
              <StatCard label="Delivered" value={formatNumber(campaignStats.delivered)} />
              <StatCard label="Opened" value={formatNumber(campaignStats.opened)} />
              <StatCard label="Clicked" value={formatNumber(campaignStats.clicked)} />
              <StatCard label="Failed" value={formatNumber(campaignStats.failed)} />
              <StatCard label="Delivery Rate" value={`${deliveryRate}%`} />
            </div>

            <div className="rounded-lg border border-brew-brown/10 bg-brew-cream p-4">
              <h3 className="text-sm font-semibold text-brew-brown">Funnel</h3>
              <div className="mt-4 space-y-4">
                <FunnelBar label="Sent" value={campaignStats.sent} max={sentCount} />
                <FunnelBar label="Delivered" value={campaignStats.delivered} max={sentCount} />
                <FunnelBar label="Opened" value={campaignStats.opened} max={sentCount} />
                <FunnelBar label="Clicked" value={campaignStats.clicked} max={sentCount} />
              </div>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}

export default CampaignsPage;
